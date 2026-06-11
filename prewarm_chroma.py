import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
fn = DefaultEmbeddingFunction()
fn(['pre-warm chroma onnx model download'])
print('Chroma ONNX model pre-downloaded')
