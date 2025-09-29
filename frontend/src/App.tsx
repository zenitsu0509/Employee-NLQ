import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { useMemo, useState } from "react";
import { AppLayout } from "./components/AppLayout";
import { ColorModeContext } from "./components/contexts/ColorModeContext";
import { Dashboard } from "./components/Dashboard";

const lightTheme = createTheme({
  palette: {
    mode: "light"
  }
});

const darkTheme = createTheme({
  palette: {
    mode: "dark"
  }
});

const App = () => {
  const [mode, setMode] = useState<"light" | "dark">("light");
  const theme = useMemo(() => (mode === "light" ? lightTheme : darkTheme), [mode]);

  const colorMode = useMemo(
    () => ({
      toggleColorMode: () => setMode((prev) => (prev === "light" ? "dark" : "light")),
      mode
    }),
    [mode]
  );

  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <AppLayout>
          <Dashboard />
        </AppLayout>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
};

export default App;
