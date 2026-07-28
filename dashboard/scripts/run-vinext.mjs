import { spawnSync } from "node:child_process";

const command = process.platform === "win32" ? "vinext.cmd" : "vinext";
const result = spawnSync(command, process.argv.slice(2), {
  env: {
    ...process.env,
    WRANGLER_LOG_PATH: ".wrangler/wrangler.log",
  },
  shell: process.platform === "win32",
  stdio: "inherit",
});

if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
