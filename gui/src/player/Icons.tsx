// Static SVG paths copied from design/player/player_mockup.html.
const paths = {
  "play": "<polygon points=\"6 3 20 12 6 21 6 3\"/>",
  "pause": "<rect x=\"14\" y=\"4\" width=\"4\" height=\"16\" rx=\"1\"/><rect x=\"6\" y=\"4\" width=\"4\" height=\"16\" rx=\"1\"/>",
  "back10": "<path d=\"M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8\"/><path d=\"M3 3v5h5\"/><text x=\"12\" y=\"15.4\" text-anchor=\"middle\" font-size=\"8\" font-weight=\"700\" font-family=\"system-ui,sans-serif\" fill=\"currentColor\" stroke=\"none\">10</text>",
  "fwd10": "<path d=\"M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8\"/><path d=\"M21 3v5h-5\"/><text x=\"12\" y=\"15.4\" text-anchor=\"middle\" font-size=\"8\" font-weight=\"700\" font-family=\"system-ui,sans-serif\" fill=\"currentColor\" stroke=\"none\">10</text>",
  "stepB": "<polygon points=\"19 20 9 12 19 4 19 20\"/><line x1=\"5\" x2=\"5\" y1=\"19\" y2=\"5\"/>",
  "stepF": "<polygon points=\"5 4 15 12 5 20 5 4\"/><line x1=\"19\" x2=\"19\" y1=\"5\" y2=\"19\"/>",
  "vol2": "<path d=\"M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z\"/><path d=\"M16 9a5 5 0 0 1 0 6\"/><path d=\"M19.364 18.364a9 9 0 0 0 0-12.728\"/>",
  "volx": "<path d=\"M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z\"/><line x1=\"22\" x2=\"16\" y1=\"9\" y2=\"15\"/><line x1=\"16\" x2=\"22\" y1=\"9\" y2=\"15\"/>",
  "fs": "<path d=\"M8 3H5a2 2 0 0 0-2 2v3\"/><path d=\"M21 8V5a2 2 0 0 0-2-2h-3\"/><path d=\"M3 16v3a2 2 0 0 0 2 2h3\"/><path d=\"M16 21h3a2 2 0 0 0 2-2v-3\"/>",
  "fsx": "<path d=\"M8 3v3a2 2 0 0 1-2 2H3\"/><path d=\"M21 8h-3a2 2 0 0 1-2-2V3\"/><path d=\"M3 16h3a2 2 0 0 1 2 2v3\"/><path d=\"M16 21v-3a2 2 0 0 1 2-2h3\"/>",
  "x": "<path d=\"M18 6 6 18\"/><path d=\"m6 6 12 12\"/>",
  "panel": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\"/><path d=\"M15 3v18\"/>",
  "split": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\"/><path d=\"M12 3v18\"/>",
  "help": "<circle cx=\"12\" cy=\"12\" r=\"10\"/><path d=\"M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3\"/><path d=\"M12 17h.01\"/>"
} as const;
export function Icon({ name }: { name: keyof typeof paths }) {
  return <svg aria-hidden="true" className={`ic ${name === "play" || name === "pause" ? "fill" : ""}`} viewBox="0 0 24 24" dangerouslySetInnerHTML={{ __html: paths[name] }} />;
}
