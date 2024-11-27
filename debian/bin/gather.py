#!/usr/bin/env python3

import argparse
import json
import pathlib
import sys


class Gather:
    def __init__(self, args):
        self._args = args

    def run(self):
        cwd = pathlib.Path.cwd()
        build = (cwd / self._args.builddir).resolve()
        source = (cwd / self._args.sourcedir).resolve()

        objects: set[pathlib.Path] = set()
        depfiles: set[pathlib.Path] = set()
        sources: set[str] = set()

        for item in self._walk(build):
            if item.is_relative_to(build / "tools"):
                # Skip host tools: XXX -- sane?
                continue
            if item.suffix not in (".cmd", ".o"):
                continue
            if item.suffix == ".o":
                objects.add(item)
            elif item.suffix == ".cmd":
                # /path/to/.thing.o.cmd -> /path/to/thing.o
                obj = item.with_name(item.stem[1:])
                if obj.suffix == ".o":
                    depfiles.add(obj)
                    sources |= self._parse_depfile(item, obj, build, source)

        if depfiles != objects:
            # Missing depfiles
            missing = sorted([str(path) for path in objects-depfiles])
            for obj in missing:
                print(f"WARN: missing sources for {obj}", file=sys.stderr)

        print(json.dumps(sorted(sources), indent=2))

    def _parse_depfile(
        self,
        depfile: pathlib.Path,
        obj: pathlib.Path,
        builddir: pathlib.Path,
        sourcedir: pathlib.Path,
    ) -> set[str]:
        # General structure is:
        #
        # savedcmd_PATH := ...
        # source_PATH := ...
        # deps_PATH := ...
        # PATH: ...
        # $(deps_PATH): ...
        #
        # Statements can be multiline: continuations marked with "\<LF><LWS>"
        # Blank lines can occur between, and terminate, statements

        # Gather statements
        statements = {}
        current_target = None
        state = "BEFORE_STATEMENT"
        for line in depfile.read_text(encoding="utf-8").splitlines():
            if state == "BEFORE_STATEMENT":
                if not line:
                    # Skip blank lines before statements
                    continue
                if line[0] == "#":
                    # Skip comments
                    continue
                if line[0] in (" ", "\t"):
                    raise ValueError(f"Unexpected continuation: '{line}'")
                # Either "thing := ..." or "thing: ..." (whitespace optional)
                target, rest = line.split(":", 1)
                current_target = target.strip()
                if rest.startswith("="):
                    # was :=
                    rest = rest[1:]
                if rest.endswith("\\"):
                    # Continuation (should) follow
                    rest = rest[:-1]
                    state = "IN_STATEMENT"
                rest = rest.strip()
                if rest:
                    statements[current_target] = [rest]
                else:
                    statements[current_target] = []
            elif state == "IN_STATEMENT":
                if not line:
                    # Blank lines terminate statements
                    state = "BEFORE_STATEMENT"
                    continue
                if line[0] not in (" ", "\t"):
                    raise ValueError(f"Unexpected non-continuation: '{line}'")
                if line.lstrip().startswith("#"):
                    # Skip comments
                    continue
                if not line.endswith("\\"):
                    # No continuation follows
                    state = "BEFORE_STATEMENT"
                else:
                    # Continuation (should) follow
                    line = line[:-1]
                line = line.strip()
                if line:
                    statements[current_target].append(line)

        # Collect sources
        sources = set()
        for statement in statements:
            # We are only interested in source_PATH and deps_PATH
            if statement.startswith("source_") or statement.startswith("deps_"):
                _, path = statement.split("_", 1)
                # Path is either relative to builddir or absolute
                if (builddir / path).resolve() != obj and path != obj.name:
                    raise ValueError(f"Unexpected target {path} in depfile for {obj}")
                for line in statements[statement]:
                    if line.startswith("$(wildcard include/config/"):
                        # Ignore lines of the form $(wildcard include/config/FOO).
                        # These are synthetic dependencies on Kconfig flag files.
                        continue
                    for source in line.split():
                        if source.startswith("/"):
                            source = pathlib.Path(source).relative_to(sourcedir)
                        else:
                            source = pathlib.Path(source)
                        sources.add(str(self._canonicalise(source)))
        return sources

    @staticmethod
    def _canonicalise(path: pathlib.Path) -> pathlib.Path:
        parts = []
        for part in path.parts:
            if part == ".":
                continue
            if part == "..":
                parts.pop()
                continue
            parts.append(part)
        if parts[0] == "/":
            # Path was absolute
            return pathlib.Path("/" + "/".join(parts[1:]))
        return pathlib.Path("/".join(parts))

    def _walk(self, root: pathlib.Path):
        for item in root.iterdir():
            if item.is_symlink():
                continue
            if item.is_file():
                yield item
            if item.is_dir():
                yield from self._walk(item)


def main():
    parser = argparse.ArgumentParser(description="Collect compiled kernel source paths")
    parser.add_argument("sourcedir", help="Path to root of kernel source tree")
    parser.add_argument("builddir", help="Path to root of kernel build tree")
    args = parser.parse_args()

    Gather(args).run()


if __name__ == "__main__":
    main()
