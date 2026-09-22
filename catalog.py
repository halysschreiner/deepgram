"""Curated prerecorded model capabilities. Sources and review date are in README."""

LANGUAGES = [
    ("pt-BR", "Português (Brasil)"), ("pt-PT", "Português (Portugal)"),
    ("en", "Inglês"), ("es", "Espanhol"), ("fr", "Francês"),
    ("de", "Alemão"), ("it", "Italiano"), ("nl", "Holandês"),
    ("ja", "Japonês"), ("ru", "Russo"), ("hi", "Hindi"),
    ("ko", "Coreano"), ("zh", "Chinês (mandarim)"),
    ("pl", "Polonês"), ("tr", "Turco"), ("uk", "Ucraniano"),
    ("sv", "Sueco"), ("da", "Dinamarquês"), ("fi", "Finlandês"),
    ("id", "Indonésio"), ("vi", "Vietnamita"),
]
MODELS = [
    {"id": "nova-3", "name": "Nova-3", "description": "Recomendado para suas gravações.",
     "languages": [code for code, _ in LANGUAGES], "multilingual": True},
    {"id": "nova-2", "name": "Nova-2", "description": "Alternativa para comparar o reconhecimento.",
     "languages": [code for code, _ in LANGUAGES if code != "tr"], "multilingual": False},
]
PRICING = {
    "checked": "2026-09-21", "source": "https://deepgram.com/pricing",
    "nova3_mono": 0.0043, "nova3_multi": 0.0052, "keyterm": 0.0013,
}
BOOLEAN_OPTIONS = (
    "smart_format", "punctuate", "paragraphs", "multichannel",
    "filler_words", "profanity_filter", "mip_opt_out",
)


def build_params(options):
    if not isinstance(options, dict):
        raise ValueError("As opções devem ser um objeto JSON.")
    allowed = set(BOOLEAN_OPTIONS) | {"model", "language", "diarize_model", "utt_split", "terms", "replacements"}
    if set(options) - allowed:
        raise ValueError("Foi enviada uma opção desconhecida.")
    model_id = options.get("model", "nova-3")
    model = next((item for item in MODELS if item["id"] == model_id), None)
    if model is None:
        raise ValueError("Selecione um modelo disponível.")
    language = options.get("language", "pt-BR")
    available = model["languages"] + ["auto"] + (["multi"] if model["multilingual"] else [])
    if language not in available:
        raise ValueError("O idioma selecionado não está disponível neste modelo.")
    params = [("model", model_id), ("utterances", "true")]
    params.append(("detect_language", "true") if language == "auto" else ("language", language))
    for key in BOOLEAN_OPTIONS:
        value = options.get(key, key in ("smart_format", "punctuate", "paragraphs"))
        if not isinstance(value, bool):
            raise ValueError("As opções de marcação devem ser verdadeiras ou falsas.")
        if key in ("filler_words", "profanity_filter") and value and language != "en":
            raise ValueError("Nesta interface, interjeições e filtro de palavrões exigem inglês explícito.")
        params.append((key, str(value).lower()))
    diarize = options.get("diarize_model", "")
    if diarize not in ("", "latest", "v1", "v2"):
        raise ValueError("Selecione uma versão válida da separação de falantes.")
    if diarize:
        params.append(("diarize_model", diarize))
    split = options.get("utt_split", 0.8)
    if isinstance(split, bool) or not isinstance(split, (int, float)) or not 0.1 <= split <= 10:
        raise ValueError("A pausa entre falas deve ficar entre 0,1 e 10 segundos.")
    params.append(("utt_split", str(split)))
    terms = options.get("terms", "")
    replacements = options.get("replacements", "")
    if not isinstance(terms, str) or len(terms) > 2000:
        raise ValueError("Reduza a lista de termos para até 2.000 caracteres.")
    if not isinstance(replacements, str) or len(replacements) > 4000:
        raise ValueError("Reduza as substituições para até 4.000 caracteres.")
    term_list = list(dict.fromkeys(term.strip() for term in terms.splitlines() if term.strip()))
    if len(term_list) > 50:
        raise ValueError("Use no máximo 50 termos, um por linha (limite adicional da API: 500 tokens no Nova-3).")
    for term in term_list:
        if ":" in term:
            raise ValueError("Informe os termos sem pesos ou dois-pontos.")
        params.append(("keyterm" if model_id == "nova-3" else "keywords", term))
    for replacement in replacements.splitlines():
        if not replacement.strip():
            continue
        parts = replacement.split("=>")
        if len(parts) != 2 or not parts[0].strip() or any(":" in part for part in parts):
            raise ValueError("Use origem => destino em cada substituição, sem dois-pontos.")
        params.append(("replace", ":".join(part.strip() for part in parts)))
    return params
