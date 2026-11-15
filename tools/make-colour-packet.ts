import { writeFile } from "node:fs/promises";
import { safeFetch } from "../src/net-http.ts";

const url = "https://www.nei.nih.gov/learn-about-eye-health/eye-conditions-and-diseases/color-blindness";
const doc = await safeFetch(url, { allowedHosts: ["www.nei.nih.gov"] });
const text = doc.body
  .replace(/<script[\s\S]*?<\/script>/gi, " ")
  .replace(/<style[\s\S]*?<\/style>/gi, " ")
  .replace(/<[^>]+>/g, " ")
  .replace(/\s+/g, " ")
  .trim();

const slice = (start: number, length = 1600) => text.slice(start, start + length);
const nei = (id: string, locator: string, start: number) => ({
  id,
  url,
  title: "Color Blindness",
  publisher: "National Eye Institute (NIH)",
  retrievedAt: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
  excerpt: slice(start),
  locator,
  snapshotHash: doc.sha256
});

const packet = {
  job: {
    topic: "Why people see colour differently",
    category: "science",
    audience: "curious general viewer",
    targetSeconds: 480,
    modelId: "qwen3.5:4b",
    voice: "af_heart"
  },
  sources: [
    {
      id: "src1",
      url: "https://spaceplace.nasa.gov/blue-sky/en/",
      title: "Why Is the Sky Blue?",
      publisher: "NASA Space Place",
      retrievedAt: "2026-11-06T01:11:14Z",
      excerpt:
        "Sunlight reaches Earth's atmosphere and is scattered in all directions by all the gases and particles in the air. Blue light is scattered more than the other colors because it travels as shorter, smaller waves. Closer to the horizon, the sky fades to a lighter blue or white. The sunlight reaching us from low in the sky has passed through even more air than the sunlight reaching us from overhead. As the Sun gets lower in the sky, its light is passing through more of the atmosphere to reach you. Even more of the blue light is scattered, allowing the reds and yellows to pass straight through to your eyes. The sky appears red because small particles of dust, pollution, or other aerosols also scatter blue light, leaving more purely red and yellow light to go through the air.",
      locator: "sections: Why is the sky blue / What makes a red sunset",
      snapshotHash: "966960a96fc4cfd72180ff8f39382ddb0ad831b7ec1f5b0126f41d753fc89a28"
    },
    {
      id: "src2",
      url: "file:///F:/AI-PROJECTS/longform-explainer/tools/numbers.md",
      title: "Numbers computed for this project",
      publisher: "This project",
      retrievedAt: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      excerpt:
        "Relative Rayleigh scattering strength scales with 1/wavelength^4, normalised to red at 675 nm: violet 400 nm 8.11, blue 450 nm 5.06, green 530 nm 2.63, yellow 580 nm 1.83, orange 620 nm 1.40, red 675 nm 1.00. Path through a flat atmosphere is 1/sin(elevation): sun overhead 1.00, 60 degrees 1.15, 45 degrees 1.41, 30 degrees 2.00, 20 degrees 2.92, 15 degrees 3.86, 10 degrees 5.76, 5 degrees 11.47. Computed with node tools/spectrum.ts on Node v24.21.0.",
      locator: "tools/numbers.md, reproducible with node tools/spectrum.ts",
      snapshotHash: "bd81b6efb830306bff5095852ea3097dfaf8d600b607050ff667dee587d5ed0b"
    },
    nei("src3", "sections: What are the types / symptoms / risk", 1700),
    nei("src4", "sections: What causes it / Did you know", 4200)
  ]
};

await writeFile("F:/AI-PROJECTS/longform-explainer/topics/why-people-see-colour-differently.packet.json", `${JSON.stringify(packet, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ nihBytes: doc.bytes, nihSha256: doc.sha256, textChars: text.length, sources: packet.sources.map((source) => [source.id, source.excerpt.length]) }));
