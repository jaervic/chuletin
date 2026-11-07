/**
 * Prueba de humo de la interfaz con Playwright.
 *
 * Requiere el backend en CHULETIN_URL y un proveedor compatible con OpenAI
 * en CHULETIN_MOCK_URL (scripts/mock_llm.py).
 *
 * Uso:
 *   SAMPLE_PDF=... node scripts/ui_smoke.mjs
 */
import { chromium } from "playwright";

const BASE = process.env.CHULETIN_URL ?? "http://127.0.0.1:8021";
const MOCK = process.env.CHULETIN_MOCK_URL ?? "http://127.0.0.1:8099/v1";
const PDF = process.env.SAMPLE_PDF;

if (!PDF) {
  throw new Error("Falta SAMPLE_PDF");
}

const problems = [];
const shots = process.env.SHOTS_DIR ?? "/tmp/opencode";

function check(condition, message) {
  if (!condition) {
    problems.push(message);
    console.error(`FALLO: ${message}`);
  } else {
    console.log(`ok: ${message}`);
  }
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
page.on("console", (message) => {
  if (message.type() === "error") problems.push(`console: ${message.text()}`);
});

try {
  await page.goto(BASE, { waitUntil: "networkidle" });
  await page
    .getByRole("heading", { name: /Pregunta lo que estés estudiando/i })
    .waitFor({ timeout: 15000 });
  check(true, "carga la pantalla inicial");

  const provider = await page.request.put(`${BASE}/api/settings/provider`, {
    data: {
      provider: "ollama",
      model: "mock-model",
      base_url: MOCK,
    },
  });
  check(provider.ok(), "configura el proveedor de pruebas");

  await page.getByRole("button", { name: "Biblioteca" }).first().click();
  await page.getByPlaceholder("Nombre de la materia").fill("Biología");
  await page.getByRole("button", { name: "Crear", exact: true }).click();

  await page.getByText("Arrastra tus archivos aquí").waitFor({ timeout: 10000 });
  check(true, "muestra la zona de subida");

  await page.locator('input[type="file"]').setInputFiles(PDF);
  await page.getByText("Listo", { exact: true }).first().waitFor({ timeout: 180000 });
  check(true, "indexa el PDF de prueba");

  await page.getByRole("button", { name: "Nueva conversación" }).click();
  const composer = page.getByPlaceholder(/Escribe tu pregunta/i);
  await composer.fill("¿Qué es la mitosis?");
  await composer.press("Enter");

  await page.getByText(/Respuesta generada por el servidor de pruebas/i).waitFor({
    timeout: 30000,
  });
  check(true, "completa la respuesta en streaming");

  await page.screenshot({ path: `${shots}/chuletin-claro.png`, fullPage: false });

  const citation = page.getByRole("button", { name: "Ver fuente 1" }).first();
  await citation.waitFor({ timeout: 10000 });
  check(true, "muestra citas clicables");

  await citation.click();
  await page.getByRole("heading", { name: "Fuente" }).waitFor({ timeout: 10000 });
  await page.waitForTimeout(1200);
  check(true, "abre el panel de la fuente");
  await page.screenshot({ path: `${shots}/chuletin-fuente.png`, fullPage: false });

  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await page
    .getByRole("button", { name: "Cambiar a tema oscuro" })
    .click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${shots}/chuletin-oscuro.png`, fullPage: false });
  check(true, "cambia al tema oscuro");

  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${shots}/chuletin-movil.png`, fullPage: false });
  check(true, "captura la vista móvil");
} catch (error) {
  problems.push(`excepción: ${error.message}`);
  console.error(error);
} finally {
  await browser.close();
}

if (problems.length) {
  console.error(`\n${problems.length} problema(s):`);
  for (const problem of problems) console.error(` - ${problem}`);
  process.exit(1);
}

console.log("\nInterfaz verificada sin errores.");
