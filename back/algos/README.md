# antiplag algorithms

This directory contains the first C++ algorithm layer for the anti-plagiarism backend.
It intentionally does not include API, workers, queues, storage, or deployment code.

## Implemented detectors

- `compare_ngrams`: fast baseline over normalized token k-grams. Covers Type-1 and Type-2 clones.
- `compare_winnowing`: MOSS-style fingerprints for long copied fragments with compact indexes.
- `compare_greedy_string_tiling`: JPlag-style matching. Produces token and line fragments for reports and is tolerant to moved blocks.
- `compare_structural`: lightweight structural skeleton matching. It is not a full AST/PDG implementation, but catches some syntax-level rewrites such as loop form changes and block movement.
- `compare_code`: weighted aggregate for candidate ranking. The worker can ignore this and use individual detector scores if the final formula is moved elsewhere.

## Why these algorithms

The attached project note describes a cascade from token methods to AST and then to PDG. For the current MVP, the selected set covers the useful part of that cascade without introducing a full static-analysis subsystem:

- Type-1: formatting and comments are handled by tokenization.
- Type-2: identifiers and literals are normalized.
- Type-3: moved or inserted code is handled by Greedy String Tiling and structural skeletons.
- Type-4: deep semantic rewrites are intentionally left for the future AI/PDG layer.

## Build and test

```sh
cd algos
make test
```

The code uses only the C++17 standard library.
