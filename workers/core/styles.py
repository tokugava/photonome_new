STYLE_LORAS: dict[str, tuple[str, str | None, float]] = {
    "flat-cartoon": (
        "Shakker-Labs/FLUX.1-Kontext-dev-LoRA-Flat-Cartoon-Style",
        None,
        1.0,
    ),
    "lego": ("Kontext-Style/LEGO_lora", None, 1.0),
    "paper-cutting": ("Kontext-Style/Paper_Cutting_lora", None, 1.0),
    "irasutoya": ("Kontext-Style/Irasutoya_lora", None, 1.0),
    "ghibli": ("Kontext-Style/Ghibli_lora", None, 1.0),
    "american-cartoon": ("Kontext-Style/American_Cartoon_lora", None, 1.0),
    "clay-toy": ("Kontext-Style/Clay_Toy_lora", None, 1.0),
}


def resolve(style: str) -> tuple[str, str | None, float]:
    try:
        return STYLE_LORAS[style]
    except KeyError as exc:
        raise ValueError(f"unknown style {style!r}; known: {sorted(STYLE_LORAS)}") from exc
