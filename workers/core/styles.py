STYLE_LORAS: dict[str, tuple[str, str | None, float]] = {
    "flat-cartoon": (
        "Shakker-Labs/FLUX.1-Kontext-dev-LoRA-Flat-Cartoon-Style",
        None,
        1.0,
    ),
}


def resolve(style: str) -> tuple[str, str | None, float]:
    try:
        return STYLE_LORAS[style]
    except KeyError as exc:
        raise ValueError(f"unknown style {style!r}; known: {sorted(STYLE_LORAS)}") from exc
