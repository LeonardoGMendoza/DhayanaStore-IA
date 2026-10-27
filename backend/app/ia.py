"""Conexão com a IA generativa da Oracle Cloud — a mesma do VinaCare e do Omni."""
import base64
import os
import threading

CHAT_MODEL = os.getenv("DHAYANA_MODELO", "cohere.command-a-03-2025")


class OracleChat:
    """Importa o SDK só no primeiro uso (os testes rodam sem ele)."""

    def __init__(self, config, compartment_id, max_tokens=700, temperature=0.4):
        self.config, self.compartment_id, self._client = config, compartment_id, None
        self.max_tokens, self.temperature = max_tokens, temperature
        self._lock = threading.Lock()

    def __call__(self, prompt):
        import oci  # noqa: PLC0415

        with self._lock:
            if self._client is None:
                oci.config.validate_config(self.config)
                self._client = oci.generative_ai_inference.GenerativeAiInferenceClient(config=self.config, timeout=(10, 45))
        m = oci.generative_ai_inference.models
        detalhe = m.ChatDetails(
            compartment_id=self.compartment_id,
            serving_mode=m.OnDemandServingMode(model_id=CHAT_MODEL),
            chat_request=m.CohereChatRequest(message=prompt, max_tokens=self.max_tokens, temperature=self.temperature))
        return self._client.chat(detalhe).data.chat_response.text.strip()


def oracle_do_ambiente(env=os.environ):
    chave = env.get("OCI_KEY_CONTENT", "")
    if not chave and env.get("OCI_KEY_B64"):
        chave = base64.b64decode(env["OCI_KEY_B64"]).decode("utf-8")
    campos = {"user": env.get("OCI_USER"), "fingerprint": env.get("OCI_FINGERPRINT"),
              "tenancy": env.get("OCI_TENANCY"), "region": env.get("OCI_REGION"), "key_content": chave}
    compartimento = env.get("OCI_COMPARTMENT_ID")
    if not all(campos.values()) or not compartimento:
        return None
    return OracleChat(campos, compartimento)
