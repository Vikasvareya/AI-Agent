import React from "react";
import { createRoot } from "react-dom/client";
import { AppearanceProvider } from "./appearance";
import "@fontsource-variable/dm-sans/wght.css";
import "@fontsource-variable/manrope/wght.css";
import App from "./App";
import "./styles.css";
import "./ui-theme.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppearanceProvider>
      <App />
    </AppearanceProvider>
  </React.StrictMode>,
);
