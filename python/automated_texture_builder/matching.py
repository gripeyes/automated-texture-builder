from __future__ import annotations

import re


IGNORED_LEADING_NAME_TOKENS = {
    "bake", "lp", "shop", "material", "materialpath", "shopmaterialpath",
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def meaningful_name_tokens(value: str) -> list[str]:
    """Remove known export/import prefixes while preserving numeric identity."""
    tokens = [
        normalize(token)
        for token in re.split(r"[_\-.\s]+", value)
        if normalize(token)
    ]
    while tokens and tokens[0] in IGNORED_LEADING_NAME_TOKENS:
        tokens.pop(0)
    return tokens


def _longest_common_token_run(left: list[str], right: list[str]) -> tuple[int, int]:
    """Return matched character count and token count for a contiguous run."""
    best = (0, 0)
    for left_index in range(len(left)):
        for right_index in range(len(right)):
            characters = 0
            count = 0
            while (
                left_index + count < len(left)
                and right_index + count < len(right)
                and left[left_index + count] == right[right_index + count]
            ):
                characters += len(left[left_index + count])
                count += 1
            best = max(best, (characters, count))
    return best


def match_materials_to_paths(
    material_paths: dict[str, str], candidates: list[str | tuple[str, bool]],
) -> dict[str, str]:
    """Find unique exact or longest meaningful partial USD-name matches."""
    matches: dict[str, str] = {}
    for set_name in material_paths:
        set_raw = normalize(set_name)
        set_tokens = meaningful_name_tokens(set_name)
        set_key = "".join(set_tokens)
        ranked: list[tuple[tuple[int, int, int, int], str]] = []
        for candidate in candidates:
            if isinstance(candidate, tuple):
                path, is_subset = candidate
            else:
                path = candidate
                is_subset = path.rsplit("/", 1)[-1].casefold().startswith("shop_materialpath")
            prim_name = path.rsplit("/", 1)[-1]
            prim_raw = normalize(prim_name)
            prim_tokens = meaningful_name_tokens(prim_name)
            prim_key = "".join(prim_tokens)
            if prim_raw == set_raw or (prim_key and prim_key == set_key):
                # An exact semantic match is equally strong with or without
                # exporter prefixes. Prefer a GeomSubset when both the parent
                # Mesh and its material partition carry the same name.
                score = (5, len(prim_key or prim_raw), len(prim_tokens), int(is_subset))
            else:
                characters, token_count = _longest_common_token_run(set_tokens, prim_tokens)
                if token_count:
                    score = (3, characters, token_count, int(is_subset))
                else:
                    shorter = min((set_key, prim_key), key=len) if set_key and prim_key else ""
                    # Safe fallback for names such as Helmet and HelmetMesh.
                    # Do not partially match numbered names (Extract1/Extract12).
                    if (
                        len(shorter) >= 6
                        and not any(character.isdigit() for character in shorter)
                        and (set_key in prim_key or prim_key in set_key)
                    ):
                        score = (2, len(shorter), 1, int(is_subset))
                    else:
                        continue
            ranked.append((score, path))
        if ranked:
            best_score = max(score for score, _ in ranked)
            best_paths = [path for score, path in ranked if score == best_score]
            if len(best_paths) == 1:
                matches[set_name] = best_paths[0]
    return matches
