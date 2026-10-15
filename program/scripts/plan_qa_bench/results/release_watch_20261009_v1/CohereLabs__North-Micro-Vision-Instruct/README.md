---
library_name: transformers
license: apache-2.0
pipeline_tag: image-text-to-text
language:
  - en
  - de
  - fr
  - es
  - it
  - pt
  - hi
  - ja
  - ko
  - zh
  - ar
tags:
  - vision
  - multimodal
  - conversational
  - multilingual
  - native-resolution
---

# North Micro Vision Instruct
![North-Micro-Vision_Hero](https://cdn-uploads.huggingface.co/production/uploads/66d732effe6684fc16b12c28/qQQSd5Pldz30hvGMhNMq_.png)

North Micro Vision Instruct is a 2.4B-parameter open-weight vision-language model with native-resolution image support, released under the Apache 2.0 license. It is designed as a compact foundation for prototyping, task-specific fine-tuning, and specialized multimodal applications.

Developed by [Cohere](https://cohere.com/).

> **Technical deep dive:** Read the [North Micro Vision technical blog post](https://huggingface.co/blog/CohereLabs/meet-north-micro-vision-instruct) for architecture, training, and evaluation details.

## Highlights

- Native-resolution image processing that preserves aspect ratios and fine visual detail.
- Broad image-understanding capabilities across VQA, captioning, grounding, OCR, charts, and documents.
- Multilingual and multi-image support.
- Compact 2.4B-parameter scale suited to customization and deployment experimentation.
- Apache 2.0-licensed model weights.

## Model Details
| Property | Value |
| --- | --- |
| Model ID | `CohereLabs/North-Micro-Vision-Instruct` |
| Total parameters | 2.4B |
| Language model | 2B parameters |
| Vision encoder | 400M parameters; custom-trained starting from [SigLIP 2 SO400M](https://huggingface.co/google/siglip2-so400m-patch16-384) |
| Inputs | Interleaved text and images |
| Output | Text |
| Languages | English, German, French, Spanish, Italian, Portuguese, Hindi, Japanese, Korean, Chinese, Arabic, and more |
| Tokenizer vocabulary size | 262,144 |
| LM Backbone context window | 128K tokens |
| Multimodal training context | 8K tokens |
| Checkpoint precision | bfloat16 |
| License | Apache 2.0 |

The language backbone supports a 128K-token context window, but the validated operating range for multimodal prompts is up to 8K tokens. Longer multimodal contexts may rely on extrapolation and have not been benchmarked.

## Quickstart

### Installation

Install [PyTorch](https://pytorch.org/get-started/locally/) for your platform first. North Micro Vision requires Transformers 5.16.0, together with `accelerate` for automatic device placement and Pillow for image loading.

Install the model code with:

```bash
uv pip install accelerate pillow "transformers==5.16.0"
```

Flash Attention 2 is optional. On supported CUDA systems, install it with:

```bash
uv pip install flash-attn --no-build-isolation
```

If you do not use `uv`, replace `uv pip` with `pip` in the commands above.

### Transformers

The following example loads an image from a URL and asks the model to describe it. Prompts can interleave text with one or more images; for text-only prompts, omit the image entries.

```python
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

model_id = "CohereLabs/North-Micro-Vision-Instruct"

processor = AutoProcessor.from_pretrained(
    model_id,
)
model = AutoModelForImageTextToText.from_pretrained(
    model_id,
    dtype="auto",
    device_map="auto",
)

# To enable Flash Attention 2, load the model with the following settings:
# model = AutoModelForImageTextToText.from_pretrained(
#     model_id,
#     dtype=torch.bfloat16,
#     attn_implementation="flash_attention_2",
#     device_map="auto",
# )

image_url = "https://cdn-uploads.huggingface.co/production/uploads/66d732effe6684fc16b12c28/Io_5OCmftsmH-n158ZtPs.png"
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "url": image_url},
            {"type": "text", "text": "What do you see?"},
        ],
    }
]

inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt",
    return_dict=True,
).to(model.device)

outputs = model.generate(
    **inputs,
    max_new_tokens=128,
    do_sample=True,
    temperature=0.7,
    top_p=0.8,
    top_k=20,
)

generated_ids = [
    output_ids[len(input_ids) :]
    for input_ids, output_ids in zip(inputs.input_ids, outputs)
]
response = processor.batch_decode(
    generated_ids,
    skip_special_tokens=True,
    clean_up_tokenization_spaces=False,
)[0]
print(response)
```

The example uses the recommended Transformers sampling settings. For deterministic output, set `do_sample=False` and omit `temperature`, `top_p`, and `top_k`.

## Architecture

North Micro Vision combines a custom-trained 400M-parameter native-resolution vision encoder with an in-house 2B-parameter language model North Micro LLM. The language model follows our Command A+ architecture, interleaving three sliding-window attention layers that use rotary positional embeddings with one global attention layer without positional embeddings. The vision encoder combines 2D RoPE with learned 1D positional embeddings to preserve spatial structure across native-resolution inputs.

The projector maps visual features into the language model's embedding space. Following DeepStack, patch embeddings from multiple vision-encoder layers are injected into corresponding early LLM layers, giving the language model access to visual representations at different levels of abstraction.

![North-Micro-Vision-Instruct-Architecture](https://cdn-uploads.huggingface.co/production/uploads/66d732effe6684fc16b12c28/hPsTh7FX3ONJXN3WfE0BX.png)
*High-level North Micro Vision architecture, consisting of a native-resolution vision encoder, a projector, and a language model.*


### Grounding Coordinates

Bounding boxes are returned as `[x1, y1, x2, y2]` on a normalized 0–1000 scale. Map them back to the original image by scaling each axis:

```python
x1_px = x1 / 1000 * image_width
y1_px = y1 / 1000 * image_height
x2_px = x2 / 1000 * image_width
y2_px = y2 / 1000 * image_height
```

### vLLM

Public vLLM support is coming soon. Until it is available, use Transformers as shown above. The recommended vLLM settings will be:

```python
temperature = 0.7
top_p = 0.8
top_k = 20
min_p = 0.0
presence_penalty = 1.5
repetition_penalty = 1.0
```

## Intended Use

North Micro Vision Instruct is intended for research and development use cases such as:

- Prototyping and task-specific fine-tuning.
- General visual question answering and image captioning.
- Multilingual and multi-image understanding.
- Visual grounding and spatial understanding.
- OCR, chart and document understanding, and structured information extraction.

## Limitations

- The model is intended as a compact foundation for customization rather than a replacement for larger general-purpose chat assistants.
- It is not a reasoning model and has limited math and code-generation capabilities.
- Tool calling and agentic workflows are not supported.
- System prompts are not recommended because the model was not trained with them, although the chat template accepts the `system` role.
- Multimodal training used an 8K-token context; longer contexts have not been validated.
- Native-resolution inputs can increase memory use and latency as image dimensions grow.

## Ecosystem Support

### Fast Inference 🚀

- [MLX-VLM model weights](https://huggingface.co/collections/mlx-community/north-micro-vision) - Community-contributed by Prince Canuma and Neywa.

### Fine-tuning

In partnership with NVIDIA, we're also shipping an AutoModel recipe for North Micro Vision, so developers can fine-tune and deploy it on NVIDIA GPUs right out of the box.

- [NVIDIA AutoModel recipe](https://github.com/NVIDIA-NeMo/Automodel/tree/main/examples/vlm_finetune/cohere_micro_vision) - Fine-tune and deploy North Micro Vision on NVIDIA GPUs.
- [Axolotl fine-tuning support](https://docs.axolotl.ai/docs/models/cohere-north-micro-vision-instruct.html) - Community-supported fine-tuning using the Axolotl framework.
  
## Benchmark Results

The complete comparison is provided below. We ran vision-language and text-only evaluations with [VLMEvalKit](https://github.com/open-compass/vlmevalkit), capping generation at 1,024 tokens; see the [technical blog post](https://huggingface.co/blog/CohereLabs/meet-north-micro-vision-instruct) for the full methodology.

<table>
    <thead>
        <tr>
            <th></th>
            <th style="font-weight: bold; background-color: rgba(127, 127, 127, 0.08);">North-Micro-Vision-Instruct</th>
            <th>Ministral-3-3B-Instruct</th>
            <th>LFM2.5-VL-1.6B</th>
            <th>Phi-3.5-vision-instruct</th>
            <th>Gemma-4-E2B-it</th>
            <th>Qwen3-VL-2B-Instruct</th>
            <th>Qwen3.5-2B-Instruct</th>
            <th>SmolVLM2.2B</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <th style="text-align: left; font-weight: normal;">Size</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">2.4B</td>
            <td>3.8B</td>
            <td>1.6B</td>
            <td>4.2B</td>
            <td>5.1B</td>
            <td>2.2B</td>
            <td>2.1B</td>
            <td>2.2B</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">License</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">Apache 2.0</td>
            <td>Apache 2.0</td>
            <td>LFM v1.0</td>
            <td>MIT</td>
            <td>Apache 2.0</td>
            <td>Apache 2.0</td>
            <td>Apache 2.0</td>
            <td>Apache 2.0</td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">General VQA</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">MMBench<sub>DEV_EN_V11</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.687</td>
            <td>0.692</td>
            <td>0.696</td>
            <td>0.731</td>
            <td>0.693</td>
            <td>0.744</td>
            <td>0.760</td>
            <td>0.674</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">MMStar</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.518</td>
            <td>0.531</td>
            <td>0.508</td>
            <td>0.495</td>
            <td>0.529</td>
            <td>0.506</td>
            <td>0.614</td>
            <td>0.460</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">RealWorldQA</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.622</td>
            <td>0.583</td>
            <td>0.642</td>
            <td>0.580</td>
            <td>0.507</td>
            <td>0.646</td>
            <td>0.693</td>
            <td>0.567</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">GQA<sub>TestDev_Balanced</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.574</td>
            <td>0.544</td>
            <td>0.395</td>
            <td>0.650</td>
            <td>0.387</td>
            <td>0.572</td>
            <td>0.539</td>
            <td>0.000<sup>&Dagger;</sup></td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">Multilingual</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">MTL<sub>MMBench_DEV</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.636</td>
            <td>0.674</td>
            <td>0.623</td>
            <td>0.619</td>
            <td>0.648</td>
            <td>0.664</td>
            <td>0.669</td>
            <td>0.454</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">MMMB</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.728</td>
            <td>0.734</td>
            <td>0.717</td>
            <td>0.686</td>
            <td>0.743</td>
            <td>0.723</td>
            <td>0.745</td>
            <td>0.577</td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">Multi-image</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">BLINK</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.527</td>
            <td>0.471</td>
            <td>0.484</td>
            <td>0.561</td>
            <td>0.468</td>
            <td>0.514</td>
            <td>0.563</td>
            <td>0.420</td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">Chart / Document / OCR</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">ChartQA<sub>Test</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.808</td>
            <td>0.791</td>
            <td>0.739</td>
            <td>0.821</td>
            <td>0.422</td>
            <td>0.693</td>
            <td>0.775</td>
            <td>0.682</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">DocVQA<sub>VAL</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.921</td>
            <td>0.896</td>
            <td>0.877</td>
            <td>0.860</td>
            <td>0.732</td>
            <td>0.825</td>
            <td>0.926</td>
            <td>0.799</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">InfoVQA<sub>VAL</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.652</td>
            <td>0.589</td>
            <td>0.627</td>
            <td>0.561</td>
            <td>0.380</td>
            <td>0.622</td>
            <td>0.731</td>
            <td>0.383</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">OCRBench<sub>v2_en</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.367</td>
            <td>0.414</td>
            <td>0.415</td>
            <td>0.339</td>
            <td>0.435</td>
            <td>0.417</td>
            <td>0.481</td>
            <td>0.304</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">OCRBench</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.792</td>
            <td>0.735</td>
            <td>0.802</td>
            <td>0.642</td>
            <td>0.719</td>
            <td>0.751</td>
            <td>0.861</td>
            <td>0.727</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">AI2D_TEST</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.775</td>
            <td>0.741</td>
            <td>0.728</td>
            <td>0.790</td>
            <td>0.712</td>
            <td>0.713</td>
            <td>0.752</td>
            <td>0.697</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">CharXiv<sub>DQ</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.600</td>
            <td>0.766</td>
            <td>0.516</td>
            <td>0.637</td>
            <td>0.751</td>
            <td>0.595</td>
            <td>0.761</td>
            <td>0.482</td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">STEM</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">MMMU<sub>DEV_VAL</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.329</td>
            <td>0.508</td>
            <td>0.380</td>
            <td>0.432</td>
            <td>0.477</td>
            <td>0.379</td>
            <td>0.474</td>
            <td>0.399</td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">Grounding / Counting</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">RefCOCO<sub>avg</sub><sup>&dagger;</sup></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.732</td>
            <td>0.317</td>
            <td>0.581</td>
            <td>0.451</td>
            <td>0.084</td>
            <td>0.304</td>
            <td>0.785</td>
            <td>0.018</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">CountBench</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.725</td>
            <td>0.737</td>
            <td>0.910</td>
            <td>0.645</td>
            <td>0.534</td>
            <td>0.848</td>
            <td>0.805</td>
            <td>0.764</td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">Robustness / Hallucination</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">HallusionBench</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.615</td>
            <td>0.652</td>
            <td>0.601</td>
            <td>0.585</td>
            <td>0.598</td>
            <td>0.673</td>
            <td>0.655</td>
            <td>0.600</td>
        </tr>
        <tr>
            <th colspan="9" style="text-align: left; background-color: rgba(127, 127, 127, 0.16);">Text</th>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">MMLU<sub>test</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.504</td>
            <td>0.660</td>
            <td>0.464</td>
            <td>0.355</td>
            <td>0.692</td>
            <td>0.630</td>
            <td>0.543</td>
            <td>0.084</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">MMLU-Pro<sub>test</sub></th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.307</td>
            <td>0.475</td>
            <td>0.199</td>
            <td>0.286</td>
            <td>0.441</td>
            <td>0.428</td>
            <td>0.298</td>
            <td>0.099</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">Multi-If</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.373</td>
            <td>0.470</td>
            <td>0.443</td>
            <td>0.304</td>
            <td>0.687</td>
            <td>0.523</td>
            <td>0.464</td>
            <td>0.236</td>
        </tr>
        <tr>
            <th style="text-align: left; font-weight: normal;">IFEval</th>
            <td style="background-color: rgba(127, 127, 127, 0.08);">0.749</td>
            <td>0.725</td>
            <td>0.776</td>
            <td>0.543</td>
            <td>0.869</td>
            <td>0.734</td>
            <td>0.679</td>
            <td>0.501</td>
        </tr>
    </tbody>
</table>
<p><small><sup>&dagger;</sup> Averaged over RefCOCO_val, RefCOCO_testA, RefCOCO_testB, RefCOCO+_val, RefCOCO+_testA, RefCOCO+_testB, RefCOCOg_val, RefCOCOg_test.</small></p>
<p><small><sup>&Dagger;</sup> SmolVLM2.2B's GQA output was scored as 0.000 under VLMEvalKit's answer-extraction rules.</small></p>



## Citation

```bibtex
@misc{cohere_north_micro_vision_instruct,
    title = {{North Micro Vision}: A 2.4B Native-Resolution Vision-Language Model},
    url = {https://huggingface.co/blog/CohereLabs/meet-north-micro-vision-instruct},
    author = {{Team Cohere}},
    month = {August},
    year = {2026}
}
```

## Contact

For errors or questions about this model card, contact [Cohere Labs](mailto:labs@cohere.com).
