const fs = require("fs");
const config = JSON.parse(fs.readFileSync("config/default.json", "utf8"));
console.log(`listening on ${config.port}`);
