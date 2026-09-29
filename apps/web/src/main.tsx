import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import { App } from "./app"
import "./styles.css"

document.documentElement.classList.remove("dark")

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
