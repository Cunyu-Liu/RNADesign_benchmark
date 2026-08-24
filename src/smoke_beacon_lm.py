"""GPU smoke test: load the 4 BEACON/RNABenchmark LM checkpoints and run a forward pass.

Each model is loaded with its official custom architecture class and tokenizer,
then a short synthetic RNA sequence is passed through for a masked-LM forward.
Prints param counts and output shapes. Exits non-zero on any failure.
"""
import os
import sys
import json
import torch

CKPT = "/mnt/cunyuliu/ToeholdDesignBench/external_src/RNABenchmark/checkpoint"
R = "/mnt/cunyuliu/ToeholdDesignBench/external_src/RNABenchmark"
sys.path.insert(0, R)

from transformers import EsmTokenizer
from tokenizer.tokenization_opensource import OpenRnaLMTokenizer

# import rnalm lazily because it requires optional flash_attn

SKIP = set(sys.argv[1:])  # pass model names to skip, e.g. BEACON-B512

SPECS = [
    ("BEACON-B512", "baseline/BEACON-B512", "rnalm", None),
    ("SpliceBERT-MS1024", "opensource/splicebert-ms1024", "splicebert-ms1024", "open"),
    ("RNA-FM", "opensource/rna-fm", "rna-fm", "open"),
    ("UTR-LM-MRL", "opensource/utr-lm-mrl", "utr-lm-mrl", "open"),
]

SEQ = "GGGGAAAUCCCGGGGAAAUCCCGGGGAAAUCCCGGGGAAAUCCCGGGGAAAUCCC"  # 54-nt synthetic

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    assert torch.cuda.is_available(), "CUDA not available - refusing CPU smoke"
    print(f"[smoke] device={device} {torch.cuda.get_device_name(0)}")

    failures = []
    for name, rel, mtype, tok_kind in SPECS:
        if name in SKIP:
            print(f"[smoke] {name}: SKIPPED (arg)")
            continue
        try:
            ckpt = os.path.join(CKPT, rel)
            if tok_kind == "open":
                tok = OpenRnaLMTokenizer.from_pretrained(ckpt)
            else:
                tok = EsmTokenizer.from_pretrained(ckpt)
            tok_params = dict(tok) if isinstance(tok, dict) else None
            # mask length via tokenizer max_len if exposed
            max_len = getattr(tok, "model_max_length", None)
            print(f"[smoke] {name}: tokenizer loaded (max_len={max_len})")

            if mtype == "rnalm":
                from model.rnalm.modeling_rnalm import RnaLmForSequenceClassification
                cls = RnaLmForSequenceClassification
            elif mtype == "splicebert-ms1024":
                from model.splicebert.modeling_splicebert import SpliceBertForSequenceClassification
                cls = SpliceBertForSequenceClassification
            elif mtype == "rna-fm":
                from model.rnafm.modeling_rnafm import RnaFmForSequenceClassification
                cls = RnaFmForSequenceClassification
            elif mtype == "utr-lm-mrl":
                from model.utrlm.modeling_utrlm import UtrLmForSequenceClassification
                cls = UtrLmForSequenceClassification
            # replicate official downstream load path (regression head, num_labels=1).
            # Official fine-tune sets attn_implementation="eager" for rnalm and
            # trains under --fp16; mirror both so the forward matches training:
            #  - rnalm WITHOUT eager -> config.attn_implementation None (KeyError)
            #  - splicebert autoselects flash_attn when installed & needs fp16
            load_kwargs = dict(num_labels=1, problem_type="regression",
                               trust_remote_code=True,
                               ignore_mismatched_sizes=True)
            if mtype == "rnalm":
                load_kwargs["attn_implementation"] = "eager"
            model = cls.from_pretrained(ckpt, **load_kwargs).to(device)
            model = model.half().eval()   # match official --fp16 regime
            nparams = sum(p.numel() for p in model.parameters())
            print(f"[smoke] {name}: loaded, params={nparams/1e6:.1f}M")

            inputs = tok(SEQ, return_tensors="pt").to(device)  # keep ids Long
            with torch.no_grad():
                out = model(**inputs, output_hidden_states=True)
            lm_out = out.logits if hasattr(out, "logits") else out
            hidden = getattr(out, "hidden_states", None)
            print(f"[smoke] {name}: forward OK logits={tuple(lm_out.shape)} hidden={None if hidden is None else tuple(hidden[-1].shape)}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            failures.append((name, str(e)))
            print(f"[smoke] {name}: FAILED - {e}")

    if failures:
        print("[smoke] RESULT: FAIL", failures)
        sys.exit(1)
    print("[smoke] RESULT: ALL 4 CHECKPOINTS LOADED AND FORWARDED OK")

if __name__ == "__main__":
    main()