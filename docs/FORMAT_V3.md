# Proposal: a confidence byte in `graph.bin`

**Status: proposed, not implemented.** `build_graph.py` computes the value and
prints its distribution, and `--confidence-sidecar` will write the full array to
`data/confidence.bin`, but nothing changes in `data/graph.bin` and the site does
not read it. This document exists because the alternative was to change the
shipped format quietly, which would have broken every cached copy of the app in
the field.

## What the number is

`build_graph.py` now shrinks each block's kernel score towards its
neighbourhood mean, with the pull set by how many incidents are actually behind
the score. The shrinkage weight falls out of that:

```
confidence = n_eff / (n_eff + k)
```

`n_eff` is the effective incident count within one bandwidth of the block, and
`k` is the fitted prior strength. Confidence near 1 means the block's score is
its own evidence. Confidence near 0 means the score is mostly borrowed from the
surrounding neighbourhood, because the block itself has almost nothing behind
it.

This is the difference between "this street is quiet" and "we have no idea about
this street and the area around it is quiet". The app currently shows those
identically, and they are not the same claim to make to a parent.

## Why it does not fit v2

`graph.bin` v2 is a header followed by eight sections, in descending alignment
order, with every offset derived from the header:

| Section | Type | Count |
|---|---|---|
| header | `uint32` | 6 |
| node lat/lon | `int32` | nNodes × 2 |
| edge u | `int32` | nEdges |
| edge v | `int32` | nEdges |
| geometry offsets | `uint32` | nEdges + 1 |
| geometry points | `int32` | nGeom × 2 |
| edge length | `uint16` | nEdges |
| street name id | `uint16` | nEdges |
| risk per window | `uint8` | nEdges × 3 |

There is no spare field, no per-edge flag byte with unused bits, and no
extension area. `app.js` rejects any version but 2 outright:

```js
if (h[1] !== 2) throw new Error(`graph format v${h[1]} is not supported`);
```

so appending a section is not backward compatible in the direction that
matters: a browser holding the old `app.js` in its service-worker cache next to
a new `graph.bin` would either fail the version check or read past the end of
the buffer. The service worker means old code and new data genuinely do meet in
the wild.

## Proposed v3

Bump the version to 3 and append one section, after risk:

| Section | Type | Count | Bytes at 431,599 edges |
|---|---|---|---|
| confidence per window | `uint8` | nEdges × 3 | 1,294,797 |

`uint8` at 1/255 resolution, matching how risk is already stored. The section
goes last so that a v2 reader pointed at a v3 file still finds every section it
knows at the offset it expects — which does not make it safe, but does make the
failure a clean version-check rejection rather than a garbled map.

Cost: +1.29 MB uncompressed on a 10.8 MB file, about +12%. The compressed cost
will be considerably lower, because confidence is spatially smooth in a way risk
is not, but the honest figure is "unmeasured until a real build runs".

### Two cheaper variants, if 12% is too much

- **One byte per block, not three.** Confidence differs between windows only
  through `n_eff`, and the windows share a spatial structure. A single
  worst-case (lowest) confidence per block costs 431,599 bytes, +4%, and still
  supports the only interaction that matters: refusing to make a confident
  claim about a thin block.
- **Four bits per window, packed two per byte.** 16 levels is finer than
  anything the interface would display. Costs +6%, at the price of a shift and
  mask in the hot decode path.

The three-byte version is the recommendation: it is the only one that keeps the
decode a straight typed-array view, which is the property the whole format was
designed around.

## What the site would do with it

Nothing automatic, and deliberately so. Confidence should change what the app
*says*, not what it routes:

- A block under ~0.3 confidence is drawn with a hatched or lightened stroke
  rather than a flat band colour.
- The street-by-street list marks such blocks "little local data" instead of
  printing a score that implies more precision than exists.
- The school report's sixteen approach directions carry the mean confidence of
  the blocks they cross, so a direction scored from thin data is not presented
  beside one scored from hundreds of incidents as if they were equally known.

Routing should keep using the shrunken score and ignore confidence. The
shrinkage has already moved thin blocks towards their neighbourhood, which is
exactly the conservative thing to do; penalising them a second time at route
time would double-count the same uncertainty.

## Taking this up

1. Add the section to the writer in `build_graph.py` (the array is already
   computed; `--confidence-sidecar` writes it today).
2. Add the read to `decode()` in `app.js`, accepting versions 2 and 3 so a
   stale cached graph still loads.
3. Bump the service worker's cache name so old code and new data cannot meet.
4. Re-run `pipeline/validate.py`, which checks that every section ends exactly
   at EOF and will catch an offset mistake immediately.
