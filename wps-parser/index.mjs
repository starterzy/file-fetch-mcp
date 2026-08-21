import { readFile } from "node:fs/promises";
import { toMarkdown, wps } from "@mdgate/wps";

const inputPath = process.argv[2];
if (!inputPath) {
  console.error("usage: node index.mjs <wps-file>");
  process.exit(2);
}

const bytes = await readFile(inputPath);
const hint = { path: inputPath };
let markdown;
try {
  // The explicit WPS converter handles OLE Kingsoft files whose metadata is
  // not sufficient for the package-level automatic sniffing.
  markdown = (await wps().convert(bytes, hint)).markdown;
} catch (error) {
  // Keep the package-level API as a secondary compatibility path.
  markdown = await toMarkdown(bytes, hint);
}
process.stdout.write(markdown);
