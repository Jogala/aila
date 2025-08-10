# %%
from datetime import datetime
from pathlib import Path

import aila.legal_analyzer as la
import aila.llm_interface as llm_interface
import aila.llm_models as llm_models
from aila.config import get_config
from aila.load_document import load_document

config = get_config()

llm_config = llm_models.default_llm_config

llm_config = llm_models.LlmConfig(
    provider_name=llm_models.ProviderName.OPENAI,
    model="gpt-4o",  # "gpt-5",  # "gpt-4o",
    temperature=0.1,
)

llm_inter = llm_interface.init_llm_interface(llm_config)

doc1_path = Path("data/1.pdf")
doc2_path = Path("data/2.pdf")
doc1 = load_document(doc1_path)
doc2 = load_document(doc2_path)
tokens_doc1 = llm_interface.count_tokens(doc1, llm_config.model)
tokens_doc2 = llm_interface.count_tokens(doc2, llm_config.model)
print(f"Tokens in Document 1: {tokens_doc1}")
print(f"Tokens in Document 2: {tokens_doc2}")

name_prompt_template = "prompt_2.txt"
prompt = la.create_analysis_prompt(doc1, doc2, name_prompt_template)

tokens_prompt = llm_interface.count_tokens(prompt, llm_config.model)
print(f"Tokens in Prompt: {tokens_prompt}")

provider_config = llm_interface.init_llm_interface(llm_config)
doc1_text = load_document(doc1_path)
doc2_text = load_document(doc2_path)

prompt = la.create_analysis_prompt(doc1_text, doc2_text, name_prompt_template)
response = provider_config.analyze_fn(prompt)
summary, changes = la.parse_llm_response(response)

result = la.AnalysisResult(
    llm_config=llm_config,
    document1_name=doc1_path.name,
    document2_name=doc2_path.name,
    changes=changes,
    summary=summary,
    analysis_timestamp=datetime.now().isoformat(),
)

print(summary.model_dump())
for v in changes:
    print(v.model_dump())

la.save_results_to_json(
    result,
    config.results_dir
    / f"{doc1_path.stem}_vs_{doc2_path.stem}_{name_prompt_template}_{result.llm_config.model_dump()}_analysis.json",
)

# %%

d = {
    "doc1_text": "This is the original contract. The payment terms are 30 days. You need to pay 1€",
    "doc2_text": "This is the updated contract. The payment terms are 1 days. You need to pay 1000000€",
    "name_doc1": "original_contract.txt",
    "name_doc2": "updated_contract.txt",
    "llm_config": {"provider_name": "anthropic", "model": "claude-3-5-haiku-20241022", "temperature": 0.1},
    "prompt_template": "prompt_1.txt",
}

result = la.analyze_documents(
    llm_interface=llm_inter,
    doc1_text=d["doc1_text"],
    doc2_text=d["doc2_text"],
    name_doc1=d["name_doc1"],
    name_doc2=d["name_doc2"],
    prompt_template=d["prompt_template"],
)

print(result.summary.model_dump())
for v in result.changes:
    print(v.model_dump())
