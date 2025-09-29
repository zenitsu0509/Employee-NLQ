import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  LinearProgress,
  Link,
  List,
  ListItem,
  ListItemText,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import HistoryIcon from "@mui/icons-material/History";

interface TableSchema {
  name: string;
  columns: string[];
  types?: Record<string, string>;
  sample_rows?: Array<Record<string, unknown>>;
}

interface SchemaPayload {
  tables: TableSchema[];
  relationships: Array<Record<string, unknown>>;
  synonyms: Record<string, string[]>;
}

interface SourceRecord {
  chunk_id?: string;
  document_id?: string;
  content?: string;
  metadata?: Record<string, unknown> | null;
  [key: string]: unknown;
}

interface QueryResponse {
  query: string;
  query_type: string;
  results: Array<Record<string, unknown>>;
  metrics: Record<string, unknown>;
  sources?: SourceRecord[] | null;
}

interface HistoryRecord {
  query: string;
  type: string;
  timestamp: number;
}

interface JobStatusResponse {
  job_id: string;
  status: string;
  processed: number;
  total: number;
  message?: string | null;
  metadata?: Record<string, unknown> | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000
});

const QUERY_SUGGESTIONS = [
  "How many employees were hired this year?",
  "Show the top 5 earners in each department",
  "Find resumes mentioning Python and AWS skills",
  "Which employees report to Sarah Connor?",
  "Average compensation by department"
];

const formatDateTime = (timestamp: number) => new Date(timestamp * 1000).toLocaleString();

export const Dashboard = () => {
  const [connectionString, setConnectionString] = useState(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("connection_string") ?? "";
  });
  const [connectionStatus, setConnectionStatus] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [schema, setSchema] = useState<SchemaPayload | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null);

  const [queryText, setQueryText] = useState(QUERY_SUGGESTIONS[0]);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  const [history, setHistory] = useState<HistoryRecord[]>([]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!connectionString) {
      localStorage.removeItem("connection_string");
      setSchema(null);
      setHistory([]);
      return;
    }

    localStorage.setItem("connection_string", connectionString);
  }, [connectionString]);

  useEffect(() => {
    if (!jobStatus || jobStatus.status === "completed" || jobStatus.status === "failed") {
      return;
    }

    const interval = window.setInterval(async () => {
      const nextStatus = await fetchJobStatus(jobStatus.job_id);
      if (nextStatus) {
        setJobStatus(nextStatus);
      }
    }, 2_000);

    return () => window.clearInterval(interval);
  }, [jobStatus]);

  useEffect(() => {
    if (!connectionString) {
      return;
    }

    void fetchHistory(connectionString).then((records) => {
      if (records) {
        setHistory(records);
      }
    });
  }, [connectionString]);

  const handleConnect = async () => {
    if (!connectionString.trim()) {
      setConnectionError("Please provide a database connection string.");
      return;
    }

    setSchemaLoading(true);
    setConnectionStatus(null);
    setConnectionError(null);
    try {
      const normalized = normalizeConnectionString(connectionString.trim());
      if (normalized !== connectionString) {
        setConnectionString(normalized);
      }
      const { data } = await api.post("/api/ingest/database", {
        connection_string: normalized
      });
      setSchema(data.schema);
      setConnectionStatus(data.message ?? "Database connected.");
      void fetchHistory(normalized).then((records) => {
        if (records) setHistory(records);
      });
    } catch (error) {
      setConnectionError(axios.isAxiosError(error) ? error.response?.data?.detail ?? error.message : String(error));
    } finally {
      setSchemaLoading(false);
    }
  };

  const handleRefreshSchema = async () => {
    if (!connectionString) return;
    setSchemaLoading(true);
    try {
      const { data } = await api.get<SchemaPayload>("/api/schema", {
        params: { connection_string: connectionString }
      });
      setSchema(data);
    } catch (error) {
      setConnectionError(axios.isAxiosError(error) ? error.response?.data?.detail ?? error.message : String(error));
    } finally {
      setSchemaLoading(false);
    }
  };

  const handleFileButtonClick = () => fileInputRef.current?.click();

  const handleFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) {
      return;
    }

    if (!connectionString) {
      setConnectionError("Connect to the database before uploading documents.");
      return;
    }

    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));
    formData.append("connection_string", connectionString);

    setUploading(true);
    setJobStatus(null);
    try {
      const { data } = await api.post<{
        job_id: string;
        status: string;
        processed: number;
        total_files: number;
      }>("/api/ingest/documents", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setJobStatus({
        job_id: data.job_id,
        status: data.status,
        processed: data.processed,
        total: data.total_files,
        message: null
      });
    } catch (error) {
      setConnectionError(axios.isAxiosError(error) ? error.response?.data?.detail ?? error.message : String(error));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRunQuery = async () => {
    if (!connectionString) {
      setQueryError("Connect to a database first.");
      return;
    }
    if (!queryText.trim()) {
      setQueryError("Please enter a natural language query.");
      return;
    }

    setQueryLoading(true);
    setQueryError(null);
    try {
      const normalized = normalizeConnectionString(connectionString);
      const { data } = await api.post<QueryResponse>("/api/query", {
        connection_string: normalized,
        query: queryText.trim(),
        top_k: 10
      });
      setQueryResult(data);
      void fetchHistory(normalized).then((records) => records && setHistory(records));
    } catch (error) {
      setQueryError(axios.isAxiosError(error) ? error.response?.data?.detail ?? error.message : String(error));
    } finally {
      setQueryLoading(false);
    }
  };

  const topMetrics = useMemo(() => {
    if (!queryResult?.metrics) return [];
    return Object.entries(queryResult.metrics).map(([key, value]) => ({
      key,
      value
    }));
  }, [queryResult]);

  return (
    <Stack spacing={3}>
      <Paper elevation={1} sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          1. Database Connection
        </Typography>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "flex-end" }}>
          <TextField
            fullWidth
            label="Connection string"
            value={connectionString}
            onChange={(event) => setConnectionString(event.target.value)}
            placeholder="postgresql+psycopg://user:pass@host:5432/employees"
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  {schemaLoading ? <CircularProgress size={18} /> : null}
                </InputAdornment>
              )
            }}
          />
          <Button variant="contained" onClick={handleConnect} disabled={schemaLoading}>
            Test & Discover Schema
          </Button>
          <Tooltip title="Refresh schema from database">
            <span>
              <IconButton onClick={handleRefreshSchema} disabled={!connectionString || schemaLoading}>
                <RefreshIcon />
              </IconButton>
            </span>
          </Tooltip>
        </Stack>
        <Box mt={2}>
          {connectionStatus ? (
            <Alert severity="success">{connectionStatus}</Alert>
          ) : null}
          {connectionError ? (
            <Alert severity="error" sx={{ mt: connectionStatus ? 1 : 0 }}>
              {connectionError}
            </Alert>
          ) : null}
        </Box>
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3, height: "100%" }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2}>
              <Typography variant="h6">2. Document Upload</Typography>
              <Button
                variant="outlined"
                startIcon={<CloudUploadIcon />}
                onClick={handleFileButtonClick}
                disabled={!connectionString || uploading}
              >
                Select files
              </Button>
            </Stack>
            <input
              type="file"
              hidden
              multiple
              ref={fileInputRef}
              onChange={handleFileSelected}
              accept=".pdf,.docx,.txt,.csv,.json,.jsonl"
            />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Supported formats: PDF, Word, text, CSV, JSON. Files are chunked and embedded automatically.
            </Typography>
            {uploading ? <LinearProgress sx={{ mt: 2 }} /> : null}
            {jobStatus ? (
              <Alert severity={jobStatus.status === "failed" ? "error" : "info"} sx={{ mt: 2 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="subtitle2">Status:</Typography>
                  <Chip
                    label={jobStatus.status.toUpperCase()}
                    color={jobStatus.status === "completed" ? "success" : jobStatus.status === "failed" ? "error" : "info"}
                    size="small"
                  />
                  <Typography variant="body2">
                    {jobStatus.processed}/{jobStatus.total} processed
                  </Typography>
                  {jobStatus.message ? <Typography variant="body2">• {jobStatus.message}</Typography> : null}
                </Stack>
              </Alert>
            ) : null}
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper elevation={1} sx={{ p: 3, height: "100%" }}>
            <Typography variant="h6" gutterBottom>
              Recent Query History
            </Typography>
            {history.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                Run a query to see history.
              </Typography>
            ) : (
              <List dense>
                {history.slice(0, 8).map((record) => (
                  <ListItem key={`${record.timestamp}-${record.query}`}>
                    <ListItemText
                      primary={record.query}
                      secondary={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Chip label={record.type.toUpperCase()} size="small" />
                          <Typography variant="caption">{formatDateTime(record.timestamp)}</Typography>
                        </Stack>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
            <Stack direction="row" spacing={1} alignItems="center" mt={2}>
              <HistoryIcon fontSize="small" color="action" />
              <Typography variant="caption" color="text.secondary">
                History is cached per connection to showcase cache hits.
              </Typography>
            </Stack>
          </Paper>
        </Grid>
      </Grid>

      <Paper elevation={1} sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          3. Ask a Question
        </Typography>
        <Stack spacing={2}>
          <TextField
            label="Natural language query"
            value={queryText}
            onChange={(event) => setQueryText(event.target.value)}
            placeholder="e.g. Show salary distribution for engineering managers"
            multiline
            minRows={2}
          />
          <Stack direction="row" spacing={1} alignItems="center">
            <Button
              variant="contained"
              startIcon={<PlayArrowIcon />}
              onClick={handleRunQuery}
              disabled={queryLoading}
            >
              Run query
            </Button>
            <Stack direction="row" spacing={1}>
              {QUERY_SUGGESTIONS.map((suggestion) => (
                <Chip key={suggestion} label={suggestion} onClick={() => setQueryText(suggestion)} clickable size="small" />
              ))}
            </Stack>
          </Stack>
          {queryLoading ? <LinearProgress /> : null}
          {queryError ? <Alert severity="error">{queryError}</Alert> : null}

          {queryResult ? (
            <Box>
              <Stack direction="row" spacing={2} alignItems="center" mb={2}>
                <Typography variant="subtitle1">Query type:</Typography>
                <Chip label={queryResult.query_type.toUpperCase()} color="primary" />
                {topMetrics.map((metric) => (
                  <Chip key={metric.key} label={`${metric.key}: ${metric.value}`} variant="outlined" />
                ))}
              </Stack>
              <Divider sx={{ mb: 2 }} />
              {queryResult.results && queryResult.results.length > 0 ? (
                <ResultsTable rows={queryResult.results} />
              ) : (
                <Typography>No structured results returned.</Typography>
              )}
              {queryResult.sources && queryResult.sources.length ? (
                <Box mt={3}>
                  <Typography variant="subtitle1" gutterBottom>
                    Document Matches
                  </Typography>
                  <Grid container spacing={2}>
                    {queryResult.sources.map((source, index) => (
                      <Grid item xs={12} md={6} key={`${source.chunk_id ?? index}`}>
                        <Card variant="outlined">
                          <CardContent>
                            <Typography variant="subtitle2" gutterBottom>
                              {source.document_id ?? "Document"}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              {String(source.content ?? "").slice(0, 320)}
                              {String(source.content ?? "").length > 320 ? "…" : ""}
                            </Typography>
                            {source.metadata ? (
                              <Stack direction="row" spacing={1} mt={1} flexWrap="wrap">
                                {Object.entries(source.metadata).map(([key, value]) => (
                                  <Chip key={key} label={`${key}: ${value}`} size="small" />
                                ))}
                              </Stack>
                            ) : null}
                          </CardContent>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              ) : null}
            </Box>
          ) : null}
        </Stack>
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} md={7}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Typography variant="h6">Discovered Schema</Typography>
              {schemaLoading ? <CircularProgress size={20} /> : null}
            </Stack>
            {!schema || schema.tables.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Connect to a database to explore tables, columns, and inferred relationships.
              </Typography>
            ) : (
              <Stack spacing={2} mt={2}>
                {schema.tables.map((table) => (
                  <Paper key={table.name} variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="subtitle1">{table.name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {table.columns.length} columns
                    </Typography>
                    <TableContainer component={Box} sx={{ mt: 1 }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Column</TableCell>
                            <TableCell>Type</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {table.columns.map((column) => (
                            <TableRow key={column}>
                              <TableCell>{column}</TableCell>
                              <TableCell>{table.types?.[column] ?? ""}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                    {table.sample_rows && table.sample_rows.length ? (
                      <Box mt={2}>
                        <Typography variant="caption" color="text.secondary">
                          Sample rows
                        </Typography>
                        <ResultsTable rows={table.sample_rows} dense />
                      </Box>
                    ) : null}
                  </Paper>
                ))}
              </Stack>
            )}
            <Box mt={2}>
              <Link href="https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls" target="_blank" rel="noreferrer">
                Learn about SQLAlchemy connection strings
              </Link>
            </Box>
          </Paper>
        </Grid>
        <Grid item xs={12} md={5}>
          <Paper elevation={1} sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Tips
            </Typography>
            <List dense>
              <ListItem>
                <ListItemText
                  primary="Schema-aware understanding"
                  secondary="The query engine maps your query to discovered tables and columns before generating SQL."
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Hybrid search"
                  secondary="Structured results come from SQL while document matches use semantic embeddings."
                />
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Caching"
                  secondary="Repeated queries are served from the cache to highlight latency improvements."
                />
              </ListItem>
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Stack>
  );
};

interface ResultsTableProps {
  rows: Array<Record<string, unknown>>;
  dense?: boolean;
}

const ResultsTable = ({ rows, dense = false }: ResultsTableProps) => {
  const columns = useMemo(() => {
    const firstRow = rows[0];
    return firstRow ? Object.keys(firstRow) : [];
  }, [rows]);

  if (columns.length === 0) {
    return null;
  }

  return (
    <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 360 }}>
      <Table size={dense ? "small" : "medium"} stickyHeader>
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell key={column}>{column}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row, rowIndex) => (
            <TableRow key={rowIndex} hover>
              {columns.map((column) => (
                <TableCell key={column}>
                  {formatCellValue(row[column])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

const formatCellValue = (value: unknown) => {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
};

const fetchHistory = async (connectionString: string) => {
  try {
    const { data } = await api.get<{ history: HistoryRecord[] }>("/api/query/history", {
      params: { connection_string: connectionString }
    });
    return data.history;
  } catch (error) {
    console.error("Failed to fetch history", error);
    return null;
  }
};

const fetchJobStatus = async (jobId: string) => {
  try {
    const { data } = await api.get<JobStatusResponse>(`/api/ingest/status/${jobId}`);
    return data;
  } catch (error) {
    console.error("Failed to fetch job status", error);
    return null;
  }
};

function normalizeConnectionString(input: string): string {
  // Ensure postgres URLs use psycopg v3 driver
  const lower = input.toLowerCase();
  if (lower.startsWith("postgresql+")) return input; // already has driver
  if (lower.startsWith("postgres+")) return input; // uncommon but already explicit
  if (lower.startsWith("postgresql://")) {
    return input.replace(/^postgresql:\/\//i, "postgresql+psycopg://");
  }
  if (lower.startsWith("postgres://")) {
    return input.replace(/^postgres:\/\//i, "postgresql+psycopg://");
  }
  return input;
}
