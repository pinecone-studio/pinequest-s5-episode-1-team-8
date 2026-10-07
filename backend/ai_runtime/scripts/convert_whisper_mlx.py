"""
Монгол Whisper-ийг (HF transformers формат) Apple MLX формат руу хөрвүүлнэ -> STT хэд дахин хурдан,
санах ой бага (M1/M2/M3). Жин нь яг хэвээрээ, зөвхөн нэр/хэлбэрийг MLX-д тааруулна.

  .venv/bin/python scripts/convert_whisper_mlx.py            # -> models/whisper-small-mn-mlx/
  .venv/bin/python scripts/convert_whisper_mlx.py <hf_repo> <out_dir>

Нэрсийн хөрвүүлэлт: ml-explore/mlx-examples whisper/convert.py (hf_to_pt)-тэй ижил.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import offline  # noqa: E402,F401

import mlx.core as mx  # noqa: E402
import numpy as np  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402
from mlx.utils import tree_flatten  # noqa: E402
from mlx_whisper import whisper  # noqa: E402
from safetensors.numpy import load_file  # noqa: E402

REPO = sys.argv[1] if len(sys.argv) > 1 else "bayartsogt/whisper-small-mn-8"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "models", "whisper-small-mn-mlx")

RENAME = [("model.", ""), (".layers", ".blocks"), (".self_attn_layer_norm", ".attn_ln"),
          (".self_attn", ".attn"), (".encoder_attn_layer_norm", ".cross_attn_ln"),
          (".encoder_attn.", ".cross_attn."), (".final_layer_norm", ".mlp_ln"),
          (".q_proj", ".query"), (".k_proj", ".key"), (".v_proj", ".value"), (".out_proj", ".out"),
          (".fc1", ".mlp1"), (".fc2", ".mlp2"), ("embed_positions.weight", "positional_embedding"),
          ("decoder.embed_tokens", "decoder.token_embedding"), ("encoder.layer_norm", "encoder.ln_post"),
          ("decoder.layer_norm", "decoder.ln")]


def main():
    src = snapshot_download(REPO)
    cfg = json.load(open(os.path.join(src, "config.json")))
    dims = {"n_mels": cfg["num_mel_bins"], "n_audio_ctx": cfg["max_source_positions"],
            "n_audio_state": cfg["d_model"], "n_audio_head": cfg["encoder_attention_heads"],
            "n_audio_layer": cfg["encoder_layers"], "n_vocab": cfg["vocab_size"],
            "n_text_ctx": cfg["max_target_positions"], "n_text_state": cfg["d_model"],
            "n_text_head": cfg["decoder_attention_heads"], "n_text_layer": cfg["decoder_layers"]}

    st = os.path.join(src, "model.safetensors")
    if os.path.exists(st):
        hf = load_file(st)
    else:                                   # хуучин snapshot: pytorch_model.bin
        import torch
        hf = {k: v.float().numpy() for k, v in
              torch.load(os.path.join(src, "pytorch_model.bin"), map_location="cpu").items()}

    out = {}
    for k, v in hf.items():
        if k == "proj_out.weight":          # token_embedding-тэй хуваалцдаг
            continue
        for a, b in RENAME:
            k = k.replace(a, b)
        if k == "encoder.positional_embedding":   # MLX-д sinusoid-оор тооцогддог (HF-д ч тогтмол)
            continue
        if "conv" in k and v.ndim == 3:     # PyTorch (out, in, k) -> MLX (out, k, in)
            v = v.swapaxes(1, 2)
        out[k] = mx.array(v.astype(np.float16))

    # Шалгалт: MLX загварын параметр бүр нэр, хэлбэрээрээ таарч байх ёстой
    expect = dict(tree_flatten(whisper.Whisper(whisper.ModelDimensions(**dims), mx.float16).parameters()))
    expect.pop("alignment_heads", None)   # жин биш, загвар өөрөө тооцно
    missing = sorted(set(expect) - set(out))
    extra = sorted(set(out) - set(expect))
    bad = [k for k in expect if k in out and expect[k].shape != out[k].shape]
    if missing or extra or bad:
        sys.exit(f"Таарахгүй: дутуу {missing[:5]}, илүү {extra[:5]}, хэлбэр {bad[:5]}")

    os.makedirs(OUT, exist_ok=True)
    mx.save_safetensors(os.path.join(OUT, "weights.safetensors"), out)
    with open(os.path.join(OUT, "config.json"), "w") as f:
        json.dump({**dims, "model_type": "whisper"}, f, indent=1)   # mlx_whisper өөр түлхүүр хүлээж авахгүй
    with open(os.path.join(OUT, "source.txt"), "w") as f:
        f.write(f"{REPO} (HF) -> scripts/convert_whisper_mlx.py\n")
    size = os.path.getsize(os.path.join(OUT, "weights.safetensors")) // 2**20
    print(f"✓ {REPO} -> {OUT} ({len(out)} тензор, {size} MB, float16)")


if __name__ == "__main__":
    main()
