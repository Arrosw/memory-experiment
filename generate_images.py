import argparse
from pathlib import Path

from diffusers import FluxPipeline
import torch


CATEGORIES = ["bowl", "mug", "pitcher", "tray", "vase"]
MATERIALS = ["wood", "metal", "glass", "ceramic", "stone"]
SEEDS = [42, 137, 256, 512, 999]

PROMPT_TEMPLATE = (
    "a single {material} {category}, studio product photography, "
    "white background, soft diffuse lighting, sharp focus, "
    "visible {material} texture, high detail, 8k, "
    "photorealistic, centered, isolated object"
)

PARAMS = {
    "width": 1024,
    "height": 1024,
    "num_inference_steps": 28,
    "guidance_scale": 3.5,
    "num_images_per_prompt": 1,
}


def load_model():
    pipe = FluxPipeline.from_pretrained(
        "black-forest-labs/FLUX.1-dev", torch_dtype=torch.float16
    )
    pipe.enable_model_cpu_offload()
    return pipe


def generate_all(pipe, categories, materials, output_dir="output"):
    base_dir = Path(output_dir)
    for category in categories:
        for material in materials:
            prompt = PROMPT_TEMPLATE.format(category=category, material=material)
            target_dir = base_dir / category / material
            existing = sorted(target_dir.glob("gen_*.png")) if target_dir.exists() else []
            if len(existing) >= len(SEEDS):
                print(f"Skipping {material} {category}: found {len(existing)} images")
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            for idx, seed in enumerate(SEEDS[len(existing):], start=len(existing) + 1):
                image = pipe(
                    prompt=prompt,
                    generator=torch.Generator("cpu").manual_seed(seed),
                    **PARAMS,
                ).images[0]
                path = target_dir / f"gen_{idx}.png"
                image.save(path)
                print(f"Saved {path}")


def parse_csv_arg(value, default):
    if not value:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or default


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--categories", default="")
    parser.add_argument("--materials", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    categories = parse_csv_arg(args.categories, CATEGORIES)
    materials = parse_csv_arg(args.materials, MATERIALS)
    if args.dry_run:
        for category in categories:
            for material in materials:
                print(PROMPT_TEMPLATE.format(category=category, material=material))
        return
    pipe = load_model()
    generate_all(pipe, categories, materials, args.output_dir)


if __name__ == "__main__":
    main()
