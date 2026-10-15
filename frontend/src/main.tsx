import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { warmUpApi } from "./api/client";
import { AuthProvider } from "./auth/AuthContext";
import "./index.css";

warmUpApi();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      {/* Sign-in and the data cache, per part of the site (buyer / seller / investor-operator) */}
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
);
