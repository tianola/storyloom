import { readFile, writeFile } from "node:fs/promises";

const path = "work/colour-draft-gw.json";
const draft = JSON.parse(await readFile(path, "utf8")) as {
  script: { chapters: { utterances: { id: string; spokenText: string; captionText: string; claimIds: string[]; scene: { props: Record<string, unknown> } }[] }[] };
};

// Reviewer edits: prose that went past the packet sources, or contradicted them.
const edits: Record<string, { spoken: string; caption: string; title?: string; steps?: string[]; claimIds?: string[] }> = {
  u023: {
    // src3: complete deficiency means seeing no color at all, and it is the rare case. The draft's second sentence said
    // people with complete deficiency still perceive some color, which is the opposite.
    spoken: "Even so, seeing nothing but gray and white is rare. That total loss comes with complete deficiency, which the sources call the uncommon case.",
    caption: "Complete loss is the rare case",
    title: "Complete deficiency is rare",
    steps: ["Complete: no color at all", "The rare case"]
  },
  u029: {
    // "a parent can carry the gene without being affected" is not in the packet; src4 says only that it is genetic and
    // passed down from parents.
    spoken: "Because the trait is genetic, it often appears across several generations of the same family. Parents pass it on, and it is usually there from early childhood.",
    caption: "Passed from parents"
  },
  u030: {
    // The X chromosome mechanism is not in the packet. src3 does say men have a much higher risk than women.
    spoken: "The pattern follows family lines. Men are affected far more often than women, which is why the condition looks so uneven across the population.",
    caption: "Men affected far more often",
    title: "Who is affected more often",
    steps: ["Runs in families", "Much higher risk in men", "Lower risk in women"]
  },
  u034: {
    // "treatment depends on the damage" and "acquired cases remain permanent" are not in the packet. src4 lists the
    // injuries and adds that color vision can worsen with age, often from cataracts.
    spoken: "When an injury to the retina, the optic nerve or the brain causes the change, the color vision follows that damage. Color vision can also get worse with age, often because of cataracts.",
    caption: "Injuries and age both change color vision",
    title: "Acquired causes",
    steps: ["Retina or optic nerve", "Brain injury", "Worse with age: cataracts"],
    claimIds: ["c17"]
  }
};

let touched = 0;
for (const chapter of draft.script.chapters) {
  for (const utterance of chapter.utterances) {
    const edit = edits[utterance.id];
    if (!edit) continue;
    utterance.spokenText = edit.spoken;
    utterance.captionText = edit.caption;
    if (edit.title) utterance.scene.props.title = edit.title;
    if (edit.steps) utterance.scene.props.steps = edit.steps;
    if (edit.claimIds) {
      utterance.claimIds = edit.claimIds;
      utterance.scene.claimIds = edit.claimIds;
    }
    touched += 1;
  }
}
if (touched !== Object.keys(edits).length) throw new Error(`expected ${Object.keys(edits).length} edits, applied ${touched}`);
await writeFile(path, JSON.stringify(draft, null, 2), "utf8");
console.log(`edited ${touched} utterances in ${path}`);
