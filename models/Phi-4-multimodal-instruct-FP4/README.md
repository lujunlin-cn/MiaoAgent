---
base_model:
- microsoft/Phi-4-multimodal-instruct
license: other
license_name: nvidia-open-model-license
license_link: >-
  https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license
library_name: Model Optimizer
tags:
- nvidia
- ModelOpt
- Phi4
- quantized
- FP4
- fp4
extra_gated_prompt: >-
  # NVIDIA Open Model License Agreement

  Version Release Date: April 28, 2025

  This NVIDIA Open Model License Agreement (the "<ins>Agreement</ins>") is a legal agreement between the Legal Entity You represent, or if no entity is identified, You and NVIDIA Corporation and its Affiliates ("<ins>NVIDIA</ins>") and governs Your use of the Models that NVIDIA provides to You under this Agreement. NVIDIA and You are each a "<ins>party</ins>" and collectively the "<ins>parties</ins>."

  NVIDIA models released under this Agreement are intended to be used permissively and enable the further development of AI technologies. Subject to the terms of this Agreement, NVIDIA confirms that:

  * Models are commercially usable.

  * You are free to create and distribute Derivative Models.

  * NVIDIA does not claim ownership to any outputs generated using the Models or Model Derivatives.

  By using, reproducing, modifying, distributing, performing or displaying any portion or element of the Model or Derivative Model, or otherwise accepting the terms of this Agreement, you agree to be bound by this Agreement.

  ## 1. Definitions

  The following definitions apply to this Agreement:

    1.1. "<ins>Phi-4-multimodal-instruct-FP8 Model</ins>" means a multimodal Model shared under this Agreement.

    1.2. "<ins>Derivative Model</ins>" means all (a) modifications to the Model, (b) works based on the Model, and (c) any other derivative works of the Model. An output is not a Derivative Model.

    1.3. "<ins>Legal Entity</ins>" means the union of the acting entity and all other entities that control, are controlled by, or are under common control with that entity. For the purposes of this definition, "<ins>control</ins>" means (a) the power, direct or indirect, to cause the direction or management of such entity, whether by contract or otherwise, or (b) ownership of fifty percent (50%) or more of the outstanding shares, or (c) beneficial ownership of such entity.

    1.4. "<ins>Model</ins>" means the machine learning model, software, checkpoints, learnt weights, algorithms, parameters, configuration files and documentation shared under this Agreement.

    1.5. "<ins>You</ins>" or "<ins>Your</ins>" means an individual or Legal Entity exercising permissions granted by this Agreement.

  ## 2. Conditions for Use, License Grant, AI Ethics and IP Ownership

    2.1. Conditions for Use. The Model and any Derivative Model are subject to additional terms as described in Section 2 and Section 3 of this Agreement and govern Your use. If You institute copyright or patent litigation against any entity (including a cross-claim or counterclaim in a lawsuit) alleging that the Model or a Derivative Model constitutes direct or contributory copyright or patent infringement, then any licenses granted to You under this Agreement for that Model or Derivative Model will terminate as of the date such litigation is filed. If You bypass, disable, reduce the efficacy of, or circumvent any technical limitation, safety guardrail or associated safety guardrail hyperparameter, encryption, security, digital rights management, or authentication mechanism contained in the Model, your rights under this Agreement will automatically terminate. NVIDIA may update this Agreement to comply with legal and regulatory requirements at any time and You agree to either comply with any updated license or cease Your copying, use, and distribution of the Model and any Derivative Model.

    2.2. License Grant. The rights granted herein are explicitly conditioned on Your full compliance with the terms of this Agreement. Subject to the terms and conditions of this Agreement, NVIDIA hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, revocable (as stated in Section 2.1) license to publicly perform, publicly display, reproduce, use, create derivative works of, make, have made, sell, offer for sale, distribute (through multiple tiers of distribution) and import the Model.

    2.3. AI Ethics. Use of the Models under the Agreement must be consistent with NVIDIA's Trustworthy AI terms found at https://www.nvidia.com/en-us/agreements/trustworthy-ai/terms/.

    2.4. NVIDIA owns the Model and any Model Derivatives created by NVIDIA. Subject to NVIDIA’s underlying ownership rights in the Model or its Model Derivatives, You are and will be the owner of Your Model Derivatives. NVIDIA claims no ownership rights in outputs. You are responsible for outputs and their subsequent uses. Except as expressly granted in this Agreement, (a) NVIDIA reserves all rights, interests and remedies in connection with the Model and (b) no other license or right is granted to you by implication, estoppel or otherwise.

  ## 3. Redistribution

  You may reproduce and distribute copies of the Model or Derivative Models thereof in any medium, with or without modifications, provided that You meet the following conditions:

    3.1. If you distribute the Model, You must give any other recipients of the Model a copy of this Agreement and include the following attribution notice within a “Notice” text file with such copies: “Licensed by NVIDIA Corporation under the NVIDIA Open Model License”;

    3.2. If you distribute or make available a Phi-4-multimodal-instruct-FP8 Model, or a product or service (including an AI model) that contains or uses a Phi-4-multimodal-instruct-FP8 Model, use a Phi-4-multimodal-instruct-FP8 Model to create a Derivative Model, or use a Phi-4-multimodal-instruct-FP8 Model or its outputs to create, train, fine tune, or otherwise improve an AI model, you will include “Built on Phi-4-multimodal-instruct-FP8” on a related website, user interface, blogpost, about page, or product documentation; and

    3.3. You may add Your own copyright statement to Your modifications and may provide additional or different license terms and conditions for use, reproduction, or distribution of Your modifications, or for any such Derivative Models as a whole, provided Your use, reproduction, and distribution of the Model otherwise complies with the conditions stated in this Agreement.

  ## 4. Separate Components.

  The Models may include or be distributed with components provided with separate legal notices or terms that accompany the components, such as an Open Source Software License or other third-party license. The components are subject to the applicable other licenses, including any proprietary notices, disclaimers, requirements and extended use rights; except that this Agreement will prevail regarding the use of third-party Open Source Software License, unless a third-party Open Source Software License requires its license terms to prevail. “Open Source Software License” means any software, data or documentation subject to any license identified as an open source license by the Open Source Initiative (https://opensource.org), Free Software Foundation (https://www.fsf.org) or other similar open source organization or listed by the Software Package Data Exchange (SPDX) Workgroup under the Linux Foundation (https://www.spdx.org).

  ## 5. Trademarks

  This Agreement does not grant permission to use the trade names, trademarks, service marks, or product names of NVIDIA, except as required for reasonable and customary use in describing the origin of the Model and reproducing the content of the “Notice” text file.

  ## **6. Disclaimer of Warranty**

  **Unless required by applicable law or agreed to in writing, NVIDIA provides the Model on an “AS IS” BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Model, Derivative Models and outputs and assume any risks associated with Your exercise of permissions under this Agreement.**

  ## **7. Limitation of Liability**

  **In no event and under no legal theory, whether in tort (including negligence), contract, or otherwise, unless required by applicable law (such as deliberate and grossly negligent acts) or agreed to in writing, will NVIDIA be liable to You for damages, including any direct, indirect, special, incidental, or consequential damages of any character arising as a result of this Agreement or out of the use or inability to use the Model, Derivative Models or outputs (including but not limited to damages for loss of goodwill, work stoppage, computer failure or malfunction, or any and all other commercial damages or losses), even if NVIDIA has been advised of the possibility of such damages.**

  ## 8. Indemnity

  You will indemnify and hold harmless NVIDIA from and against any claim by any third party arising out of or related to your use or distribution of the Model, Model Derivatives or outputs.

  ## 9. Feedback

  NVIDIA appreciates your feedback, and You agree that NVIDIA may use it without restriction or compensation to You.

  ## 10. Governing Law

  This Agreement will be governed in all respects by the laws of the United States and the laws of the State of Delaware, without regard to conflict of laws principles or the United Nations Convention on Contracts for the International Sale of Goods. The state and federal courts residing in Santa Clara County, California will have exclusive jurisdiction over any dispute or claim arising out of or related to this Agreement, and the parties irrevocably consent to personal jurisdiction and venue in those courts; except that, either party may apply for injunctive remedies or an equivalent type of urgent legal relief in any jurisdiction.

  ## 11. Trade and Compliance

  You agree to comply with all applicable export, import, trade and economic sanctions laws and regulations, as amended, including without limitation U.S. Export Administration Regulations and Office of Foreign Assets Control regulations. These laws include restrictions on destinations, end-users and end-use.
extra_gated_fields:
  By clicking Submit below, I accept the terms of the NVIDIA Open Model License Agreement and acknowledge that I am an adult of legal age of majority in the country in which the Phi-4-multimodal Models will be used and have authority to accept this Agreement: checkbox
extra_gated_description: >-
  The information you provide will be collected, stored, processed and shared in accordance with the [NVIDIA Privacy Policy](https://www.nvidia.com/en-us/about-nvidia/privacy-policy/).
extra_gated_button_content: Submit
---
# Model Overview

## Description:
The NVIDIA Phi-4-multimodal-instruct FP4 model is the quantized version of Microsoft’s Phi-4-multimodal-instruct model, which is a multimodal foundation model that uses an optimized transformer architecture. For more information, please check [here](https://huggingface.co/microsoft/Phi-4-multimodal-instruct). The NVIDIA Phi-4-multimodal-instruct FP4 model is quantized with [TensorRT Model Optimizer](https://github.com/NVIDIA/TensorRT-Model-Optimizer).

This model is ready for commercial/non-commercial use.  <br>

## Third-Party Community Consideration
This model is not owned or developed by NVIDIA. This model has been developed and built to a third-party’s requirements for this application and use case; see link to Non-NVIDIA [(Phi-4-multimodal-instruct) Model Card](https://huggingface.co/microsoft/Phi-4-multimodal-instruct).

### License/Terms of Use:
Use of this model is governed by [nvidia-open-model-license](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/)
ADDITIONAL INFORMATION: [MIT_License](https://huggingface.co/api/resolve-cache/models/microsoft/Phi-4-multimodal-instruct/33e62acdd07cd7d6635badd529aa0a3467bb9c6a/LICENSE?%2Fmicrosoft%2FPhi-4-multimodal-instruct%2Fresolve%2Fmain%2FLICENSE=&etag=%229e841e7a26e4eb057b24511e7b92d42b257a80e5%22).

### Deployment Geography:
Global, except in European Union <br>

### Use Case: <br>
Developers looking to take off the shelf pre-quantized models for deployment in AI Agent systems, chatbots, RAG systems, and other AI-powered applications. <br>

### Release Date:  <br>
Huggingface 09/15/2025 via https://huggingface.co/nvidia/Phi-4-multimodal-instruct-FP4 <br> 

## Model Architecture:
**Architecture Type:** Transformers  <br>
**Network Architecture:** Phi4MMForCausalLM<br>

**This model was developed based on Phi-4-multimodal-instruct
** Number of model parameters 5.6*10^9

## Input:
**Input Type(s):** Text, image and speech <br>
**Input Format(s):** String, Images (see properties), Soundfile <br>
**Input Parameters:** One-Dimensional (1D), Two-Dimensional (2D), One-Dimensional (1D) <br>
**Other Properties Related to Input:** Any common RGB/gray image format (e.g., (".jpg", ".jpeg", ".png", ".ppm", ".bmp", ".pgm", ".tif", ".tiff", ".webp")) can be supported. Any audio format that can be loaded by soundfile package should be supported. Context length up to 128K <br>

## Output:
**Output Type(s):** Text <br>
**Output Format:** String <br>
**Output Parameters:** 1D (One-Dimensional): Sequences <br>
**Other Properties Related to Output:** N/A <br>

Our AI models are designed and/or optimized to run on NVIDIA GPU-accelerated systems. By leveraging NVIDIA’s hardware (e.g. GPU cores) and software frameworks (e.g., CUDA libraries), the model achieves faster training and inference times compared to CPU-only solutions. <br>  

## Software Integration:
**Supported Runtime Engine(s):** <br>
* TensorRT-LLM <br>

**Supported Hardware Microarchitecture Compatibility:** <br>
* NVIDIA Blackwell <br>

**Preferred Operating System(s):** <br>
* Linux <br>

## Model Version(s):
The model is quantized with nvidia-modelopt **v0.35.0**  <br>

## Post Training Quantization
This model was obtained by quantizing the weights and activations of Phi-4-multimodal-instruct to FP4 data type, ready for inference with TensorRT-LLM. Only the weights and activations of the linear operators within transformer blocks of the language model are quantized.

## Training and Testing Datasets:
** Data Modality
[Audio]
[Image]
[Text]
** Text Training Data Size 
[1 Billion to 10 Trillion Tokens]
** Audio Training Data Size 
[More than 1 Million Hours]
** Image Training Data Size 
[1 Billion to 10 Trillion image-text Tokens]
## Calibration Dataset: 
** Link: [cnn_dailymail](https://huggingface.co/datasets/abisee/cnn_dailymail) <br>
** Data collection method: Automated. <br>
** Labeling method: Automated. <br>

## Training Datasets:
** Data Collection Method by Dataset: Automated <br>
** Labeling Method by Dataset: Human, Automated <br>
** Properties: publicly available documents filtered for quality, selected high-quality educational data, and code
* newly created synthetic, “textbook-like” data for the purpose of teaching math, coding, common sense reasoning, general knowledge of the world (e.g., science, daily activities, theory of mind, etc.)
* high quality human labeled data in chat format
* selected high-quality image-text interleave data
* synthetic and publicly available image, multi-image, and video data
* anonymized in-house speech-text pair data with strong/weak transcriptions
* selected high-quality publicly available and anonymized in-house speech data with task-specific supervisions
* selected synthetic speech data
* synthetic vision-speech data

## Testing Dataset:
** Data Collection Method by Dataset: Undisclosed <br>
** Labeling Method by Dataset: Undisclosed <br>
** Properties: Undisclosed <br>

## Inference:
**Engine:** TensorRT-LLM <br>
**Test Hardware:** B200 coming soon <br>
** Currently supported on DGX Spark <br>

## Usage

### Deploy with TensorRT-LLM

To deploy the quantized checkpoint with [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM) LLM API, follow the sample codes below:

* LLM API sample usage:
```
from tensorrt_llm import LLM, SamplingParams


def main():

    prompts = [
        "Hello, my name is",
        "The president of the United States is",
        "The capital of France is",
        "The future of AI is",
    ]
    sampling_params = SamplingParams(temperature=0.8, top_p=0.95)

    llm = LLM(model="nvidia/Phi-4-multimodal-instruct-FP4", trust_remote_code=True)

    outputs = llm.generate(prompts, sampling_params)

    # Print the outputs.
    for output in outputs:
        prompt = output.prompt
        generated_text = output.outputs[0].text
        print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")


# The entry point of the program needs to be protected for spawning processes.
if __name__ == '__main__':
    main()

```

## Ethical Considerations

NVIDIA believes Trustworthy AI is a shared responsibility and we have established policies and practices to enable development for a wide array of AI applications.  When downloaded or used in accordance with our terms of service, developers should work with their internal model team to ensure this model meets requirements for the relevant industry and use case and addresses unforeseen product misuse.
Please report model quality, risk, security vulnerabilities or NVIDIA AI Concerns here.  
