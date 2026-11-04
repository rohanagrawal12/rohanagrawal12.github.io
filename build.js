const fs = require("fs");
const src = fs.readFileSync("index.src.html", "utf8");
const data = JSON.parse(fs.readFileSync("data/opportunities.json", "utf8"));
const DATA = {
  school: data.school,
  community: data.community,
  explore: data.explore,
  extra_opportunities_not_enough_info: data.extra_opportunities_not_enough_info
};
if (!src.includes("__DATA__")) {
  console.error("index.src.html is missing the __DATA__ placeholder");
  process.exit(1);
}
fs.writeFileSync("index.html", src.replace("__DATA__", JSON.stringify(DATA)));
console.log("Wrote index.html");
