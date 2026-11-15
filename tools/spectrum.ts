const reference = 675;
const rel = (lambda: number) => Math.pow(reference / lambda, 4);
const secant = (elevationDegrees: number) => 1 / Math.sin((elevationDegrees * Math.PI) / 180);

const bands: [string, number][] = [
  ["violet", 400],
  ["blue", 450],
  ["green", 530],
  ["yellow", 580],
  ["orange", 620],
  ["red", 675]
];

const rows = bands.map(([name, lambda]) => `${name} ${lambda} nm  scattering ${rel(lambda).toFixed(2)}`);
const angles = [90, 60, 45, 30, 20, 15, 10, 5];
const paths = angles.map((degrees) => `sun ${degrees} degrees above the horizon  path ${secant(degrees).toFixed(2)}`);

console.log(rows.join("\n"));
console.log("");
console.log(paths.join("\n"));
console.log("");
console.log(`ratio blue/red ${(rel(450) / rel(675)).toFixed(2)}`);
console.log(`path 10 degrees divided by overhead ${secant(10).toFixed(2)}`);
console.log(`wavelength sweep 400..700 step 50`);
for (let lambda = 400; lambda <= 700; lambda += 50) console.log(`  ${lambda} nm  ${rel(lambda).toFixed(3)}`);
