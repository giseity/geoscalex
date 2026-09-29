import { createDeepSeekGenerator } from "./service.js"
import { createGatewayServer } from "./server.js"

const host = process.env.MODEL_GATEWAY_HOST ?? "127.0.0.1"
const port = Number(process.env.MODEL_GATEWAY_PORT ?? "8001")
const generator = process.env.DEEPSEEK_API_KEY ? createDeepSeekGenerator() : null

createGatewayServer(generator).listen(port, host, () => {
  console.log(`GeoScaleX model gateway ready at http://${host}:${port} (${generator ? "configured" : "no key"})`)
})
