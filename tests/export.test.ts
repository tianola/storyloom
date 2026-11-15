import assert from "node:assert/strict";
import { test } from "node:test";
import { buildAssemblyCommand, buildChaptersMetadata, buildConcatList, verifyExport } from "../src/export.ts";

const probe = {
  format: { duration: "120.02", nb_streams: "2" },
  streams: [
    { index: 0, codec_type: "video", codec_name: "h264", width: 1920, height: 1080, avg_frame_rate: "30/1", nb_frames: "3600", sample_rate: undefined, channels: undefined },
    { index: 1, codec_type: "audio", codec_name: "aac", sample_rate: "48000", channels: "2", avg_frame_rate: undefined, width: undefined, height: undefined, nb_frames: undefined }
  ]
};

const expected = { durationSeconds: 120, frameRate: 30, totalFrames: 3600, sampleRate: 48000, videoStreams: 1, audioStreams: 1 };

test("concat list carries real durations and chapter blocks are frame-quantized", () => {
  const list = buildConcatList([
    { path: "work/s1.mp4", durationSeconds: 2.5 },
    { path: "work/s2.mp4", durationSeconds: 3 }
  ]);
  assert.equal(list, "ffconcat version 1.0\nfile 'work/s1.mp4'\nduration 2.500\nfile 'work/s2.mp4'\nduration 3.000\n");
  assert.ok(!list.endsWith("file 'work/s2.mp4'\n"), "repeating the last video file appends a whole extra scene");
  assert.throws(() => buildConcatList([{ path: "work/x.mp4", durationSeconds: 0 }]), /positive duration/);

  const chapters = buildChaptersMetadata(
    [
      { startSeconds: 0, title: "Intro" },
      { startSeconds: 60.033, title: "The  Mechanism" }
    ],
    { frameRate: 30, durationSeconds: 120.02 }
  );
  assert.match(chapters, /^;FFMETADATA1/);
  assert.equal(chapters.split("\n").filter((line) => line === "[CHAPTER]").length, 2);
  assert.ok(chapters.includes("TIMEBASE=1/1000"), chapters);
  assert.ok(chapters.includes("START=60000"), `frame-quantized start missing from ${chapters}`);
  assert.ok(chapters.includes("END=120020"), `the last chapter must end at the real duration: ${chapters}`);
  assert.ok(chapters.includes("title=The Mechanism"));
  assert.ok(!chapters.includes("Start="), "FFmpeg 9 reads only uppercase START/END keys");
  assert.ok(!chapters.includes("9223372036854775807"), "no integer-overflow sentinel end time");
  assert.throws(
    () => buildChaptersMetadata([{ startSeconds: 5, title: "Only" }], { frameRate: 30, durationSeconds: 5 }),
    /ends at or before it starts/
  );
});

test("assembly pins sample rate, frame rate, loudness and faststart into a temporary file", () => {
  const args = buildAssemblyCommand({
    concatList: "work/concat.txt",
    chapters: "work/chapters.txt",
    masterAudio: "work/master.wav",
    output: "exports/video.mp4",
    frameRate: 30,
    sampleRate: 48000,
    targetLufs: -15
  });
  const joined = args.join(" ");
  assert.equal(args[0], "ffmpeg");
  assert.match(joined, /-f concat -safe 0 -i work\/concat\.txt/);
  assert.match(joined, /-i work\/master\.wav/);
  assert.match(joined, /-map_metadata 1/);
  assert.match(joined, /-ar 48000/);
  assert.match(joined, /-r 30/);
  assert.match(joined, /-af loudnorm=I=-15/);
  assert.match(joined, /-movflags \+faststart/);
  assert.equal(args.at(-1), "exports/video.mp4.part");
  assert.equal(args.slice(-3).join(" "), `-f mp4 ${args.at(-1)}`, "a .part suffix hides the container from the format probe");
});

test("a validated export has no problems", () => {
  const result = verifyExport({ probe, expected, distinctFrameDigests: 120, sampledFrames: 120 });
  assert.deepEqual(result.problems, []);
  assert.equal(result.ok, true);
});

test("zero or missing duration never passes as success", () => {
  const broken = { ...probe, format: { duration: "0", nb_streams: "2" } };
  const result = verifyExport({ probe: broken, expected, distinctFrameDigests: 40, sampledFrames: 40 });
  assert.ok(result.problems.some((problem) => problem.code === "duration-missing"));
});

test("duration drift, missing audio and blank output are reported", () => {
  const cases = [
    { probe: { ...probe, format: { duration: "180", nb_streams: "2" } }, distinctFrameDigests: 120, sampledFrames: 120 },
    { probe: { ...probe, streams: [probe.streams[0]!] }, distinctFrameDigests: 100, sampledFrames: 100 },
    { probe, distinctFrameDigests: 1, sampledFrames: 60 }
  ];
  const problems = cases.map((case_) => verifyExport({ ...case_, expected }).problems.map((problem) => problem.code));
  assert.ok(problems[0]?.includes("duration-drift"));
  assert.ok(problems[1]?.includes("audio-stream-missing"));
  assert.ok(problems[2]?.includes("blank-frames"));
});

test("frame rate, frame count and sample rate mismatches are caught", () => {
  const wrongRate = { ...probe, streams: [{ ...probe.streams[0]!, avg_frame_rate: "25/1" }, probe.streams[1]!] };
  const shortVideo = { ...probe, streams: [{ ...probe.streams[0]!, nb_frames: "1200" }, probe.streams[1]!] };
  const wrongAudio = { ...probe, streams: [probe.streams[0]!, { ...probe.streams[1]!, sample_rate: "44100" }] };
  for (const [probe_, code] of [[wrongRate, "frame-rate-mismatch"], [shortVideo, "frame-count-mismatch"], [wrongAudio, "sample-rate-mismatch"]] as const) {
    const result = verifyExport({ probe: probe_, expected, distinctFrameDigests: 60, sampledFrames: 60 });
    assert.ok(result.problems.some((problem) => problem.code === code), code);
  }
});
