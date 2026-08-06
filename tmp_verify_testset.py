import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, 'src')
from evaluation.testset import build_test_set


df = pd.DataFrame([
    {
        'paper_id': '10.1000/example1',
        'title': 'Agentic retrieval augmented generation for scientific search',
        'summary': 'This paper describes a practical agentic retrieval pipeline for scientific search.',
        'authors': ['Alice Nguyen', 'Bob Chen'],
        'categories': ['Computer Science', 'Information Retrieval'],
        'published': '2024-05-01',
    },
    {
        'paper_id': '10.1000/example2',
        'title': 'Evaluating retrieval quality in large language models',
        'summary': 'The paper studies evaluation metrics and quality checks for retrieval systems.',
        'authors': ['Carol Kim'],
        'categories': ['Machine Learning'],
        'published': '2023-08-15',
    },
    {
        'paper_id': '10.1000/example3',
        'title': 'Improving RAG with structured knowledge',
        'summary': 'This article explains how structured knowledge improves retrieval-augmented generation.',
        'authors': ['Derek Liu', 'Eva Rao'],
        'categories': ['Natural Language Processing'],
        'published': '2022-11-03',
    },
    {
        'paper_id': '10.1000/example4',
        'title': 'Scaling vector search for enterprise applications',
        'summary': 'The study focuses on efficient vector search systems for enterprise workloads.',
        'authors': ['Fiona Patel'],
        'categories': ['Systems'],
        'published': '2024-01-20',
    },
    {
        'paper_id': '10.1000/example5',
        'title': 'Observed failures in data quality for retrieval pipelines',
        'summary': 'This work highlights failures caused by inconsistent data quality in retrieval pipelines.',
        'authors': ['George Flores', 'Hana Ortiz'],
        'categories': ['Data Engineering'],
        'published': '2021-06-09',
    },
])

out = Path('data/eval/test_set.json')
samples = build_test_set(df, out)
print('samples', len(samples))
print(samples[0])
print('exists', out.exists())
