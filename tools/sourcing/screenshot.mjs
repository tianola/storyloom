import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { chromium } from "playwright";

function parseArguments(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    if (flag !== "--url" && flag !== "--out") {
      throw new Error("usage: node tools/sourcing/screenshot.mjs --url <http(s)-or-file-URL> --out <local.png>");
    }
    if (!argv[index + 1]) throw new Error(`${flag} requires a value`);
    values[flag] = argv[index + 1];
  }
  if (!values["--url"] || !values["--out"]) {
    throw new Error("usage: node tools/sourcing/screenshot.mjs --url <http(s)-or-file-URL> --out <local.png>");
  }
  return values;
}

async function capture(url, output) {
  const protocol = new URL(url).protocol;
  if (!["http:", "https:", "file:"].includes(protocol)) {
    throw new Error("screenshot URL must use http, https, or file");
  }
  const destination = resolve(output);
  await mkdir(dirname(destination), { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: destination, fullPage: true, type: "png" });
  } finally {
    await browser.close();
  }
  return destination;
}

try {
  const values = parseArguments(process.argv.slice(2));
  const destination = await capture(values["--url"], values["--out"]);
  console.log(destination);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
