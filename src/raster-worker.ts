import { parentPort } from "node:worker_threads";
import { Resvg } from "@resvg/resvg-js";

type Job = { index: number; svg: string; width: number; height: number };

parentPort?.on("message", (job: Job) => {
  try {
    const resvg = new Resvg(job.svg, {
      fitTo: { mode: "width", value: job.width },
      font: { loadSystemFonts: true, defaultFontFamily: "sans-serif" }
    });
    const drawn = resvg.render().asPng();
    const bytes = new Uint8Array(drawn);
    parentPort?.postMessage({ index: job.index, bytes }, [bytes.buffer]);
  } catch (error) {
    parentPort?.postMessage({ index: job.index, error: error instanceof Error ? error.message : String(error) });
  }
});
