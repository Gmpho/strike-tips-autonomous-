import os
import pytest
from core_agent.skills.bankroll_manager.governor import BankrollGovernor
from core_agent.skills.memory.chroma_memory import RacingMemory
from core_agent.core.strike_brain import brain

def test_dsi_stake_scaling(tmp_path):
    # Set up temp data directory for governor and chroma database
    temp_dir = str(tmp_path / "data")
    os.makedirs(temp_dir, exist_ok=True)
    chroma_dir = os.path.join(temp_dir, "chroma")
    
    # Clear Chroma HTTP env vars to force a local persistent client for the test
    old_host = os.environ.pop("CHROMA_HOST", None)
    old_key = os.environ.pop("CHROMA_API_KEY", None)
    
    # Mock embedding function to prevent Ollama requests and HuggingFace ONNX downloads
    from core_agent.skills.memory import chroma_memory
    from chromadb import EmbeddingFunction
    
    class MockEmbeddingFn(EmbeddingFunction):
        def __call__(self, input):
            return [[0.0] * 384 for _ in input]
            
    chroma_memory._make_embedding_fn = lambda: MockEmbeddingFn()

    try:
        memory = RacingMemory(data_dir=chroma_dir)
        brain.memory = memory
        assert brain.memory._is_ready is True
    finally:
        if old_host:
            os.environ["CHROMA_HOST"] = old_host
        if old_key:
            os.environ["CHROMA_API_KEY"] = old_key
    
    track = "test_dsi_track"
    race_number = 3
    
    # Add mock dreams: 3 negative, 1 positive -> DSI = 75%
    brain.memory.add_form_insight(
        horse=f"dream_{track}_r{race_number}_1",
        insight="Scenario: Heavy rain. Shift: -0.05",
        metadata={"type": "dream", "track": track, "race": str(race_number), "probability_shift": -0.05}
    )
    brain.memory.add_form_insight(
        horse=f"dream_{track}_r{race_number}_2",
        insight="Scenario: Headwinds. Shift: -0.06",
        metadata={"type": "dream", "track": track, "race": str(race_number), "probability_shift": -0.06}
    )
    brain.memory.add_form_insight(
        horse=f"dream_{track}_r{race_number}_3",
        insight="Scenario: Late scratch. Shift: -0.02",
        metadata={"type": "dream", "track": track, "race": str(race_number), "probability_shift": -0.02}
    )
    brain.memory.add_form_insight(
        horse=f"dream_{track}_r{race_number}_4",
        insight="Scenario: Mud expert. Shift: 0.08",
        metadata={"type": "dream", "track": track, "race": str(race_number), "probability_shift": 0.08}
    )
    
    gov = BankrollGovernor(data_dir=temp_dir, starting_bankroll=1000.0)
    
    # Base unstressed stake (no track/race provided)
    base_stake = gov.calculate_max_stake(edge_percent=8.0)
    assert base_stake == 40.0
    
    # Stressed stake (under 75% DSI)
    stressed_stake = gov.calculate_max_stake(edge_percent=8.0, track=track, race_number=race_number)
    
    # Sizing should scale by exactly 0.50x
    assert stressed_stake == 20.0
