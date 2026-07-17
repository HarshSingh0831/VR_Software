# Public-data and headset fine-tuning workflow

## What is prepared now

FER2013 has been downloaded and converted into the same two grayscale regions
available to the headset:

- `upper_face`: eyes and eyebrows
- `lower_face`: lips, mouth, and chin

The converter preserves the public train, validation, and test splits. It does
not rename facial expressions as engagement states. FER2013 therefore trains an
auxiliary seven-class `expression` task, not the final 12-class `vr_state` task.

Local artifacts are under the ignored `models/` directory:

```text
models/downloads/fer2013/              Original Parquet shards
models/datasets/fer2013_vr/manifest.csv
models/datasets/fer2013_vr/images/     71,774 region images
models/trained/                         Models and JSON evaluation reports
```

## Rebuild and train

```powershell
.venv\Scripts\python.exe -m adaptive_vr.public_dataset fer2013-parquet `
  --input models\downloads\fer2013\train-00000-of-00001.parquet `
  --input models\downloads\fer2013\valid-00000-of-00001.parquet `
  --input models\downloads\fer2013\test-00000-of-00001.parquet `
  --output models\datasets\fer2013_vr

.venv\Scripts\python.exe -m adaptive_vr.train_baseline `
  --manifest models\datasets\fer2013_vr\manifest.csv `
  --output models\trained --task expression --region upper_face

.venv\Scripts\python.exe -m adaptive_vr.train_baseline `
  --manifest models\datasets\fer2013_vr\manifest.csv `
  --output models\trained --task expression --region lower_face

.venv\Scripts\python.exe -m adaptive_vr.evaluate_fusion `
  --manifest models\datasets\fer2013_vr\manifest.csv `
  --model-dir models\trained --task expression --split test
```

## Import real headset sessions

Download one or more Pi calibration session directories, then build the
subject-separated `vr_state` manifest:

```powershell
.venv\Scripts\python.exe -m adaptive_vr.headset_dataset `
  --session data\calibration\P001_session_01 `
  --session data\calibration\P002_session_01 `
  --output models\datasets\headset_vr
```

The same trainer accepts `--task vr_state`. Keep every participant entirely in
one split; never put frames from one person in both training and evaluation.

## Dataset access still requiring the researcher

- DAiSEE is approximately 15 GB. IIT Hyderabad requires a researcher to fill
  in its form and accept research-use and redistribution conditions before the
  download is provided: <https://people.iith.ac.in/vineethnb/resources/daisee/>
- AffectNet requires an individual academic-use agreement. Access cannot be
  accepted by software on a researcher's behalf:
  <https://mohammadmahoor.com/affectnet/>

Their labels must remain separate tasks (`engagement` and
`expression_valence_arousal`) until the multimodal fusion stage.

## Current measured models

The untouched FER2013 test split contains 3,589 faces. Current CPU linear
baseline results are:

| View | Accuracy | Macro F1 |
|---|---:|---:|
| Upper face | 22.57% | 20.99% |
| Lower face | 25.72% | 23.97% |
| Equal probability fusion | 25.55% | 24.12% |

This baseline validates the data and evaluation plumbing. It is not accurate
enough for deployment. The next model upgrade is a compact CNN followed by
temporal and multimodal fine-tuning on DAiSEE and real headset sessions.

The compact 17,415-parameter CNN has now been trained for each camera. On the
same untouched 3,589-face FER2013 test split:

| CNN view | Accuracy | Macro F1 |
|---|---:|---:|
| Upper face | 31.46% | 28.23% |
| Lower face | 39.15% | 30.93% |
| Equal probability fusion | 42.13% | 35.66% |

Checkpoints, training histories, TorchScript inference models, and fusion
metrics are stored in `models/cnn/`. Run a synchronized image pair with:

```powershell
.venv\Scripts\python.exe -m adaptive_vr.cnn_inference `
  --model-dir models\cnn `
  --upper path\to\upper_face.pgm `
  --lower path\to\lower_face.pgm
```

These outputs are seven-class expression probabilities. They are inputs to the
later engagement/VR-state fusion model, not direct replacements for the 12
student-state labels.
