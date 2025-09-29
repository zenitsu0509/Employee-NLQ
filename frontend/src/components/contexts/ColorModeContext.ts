import { createContext } from "react";

export const ColorModeContext = createContext<{
  mode: "light" | "dark";
  toggleColorMode: () => void;
} | null>(null);
