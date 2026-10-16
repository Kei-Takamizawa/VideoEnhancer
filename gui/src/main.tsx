import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./ErrorBoundary";
import "./style.css";
createRoot(document.getElementById("root")!).render(<ErrorBoundary scope="App"><App /></ErrorBoundary>);
