import copy

import torch
from torch.utils.data import DataLoader

from src.federated.client import FederatedClient
from src.federated.fedavg import federated_average
from src.federated.server import FederatedServer
from src.models.cnn import build_model


def test_local_train_changes_parameters(tiny_dataset):
    loader = DataLoader(tiny_dataset, batch_size=16, shuffle=True)
    client = FederatedClient(client_id=0, data_loader=loader)
    model = build_model()
    before = copy.deepcopy(model.state_dict())

    result = client.local_train(model, local_epochs=1, lr=0.1)

    changed = any(not torch.allclose(before[k], result.state_dict[k]) for k in before)
    assert changed
    assert result.num_samples == len(tiny_dataset)


def test_fedavg_matches_manual_weighted_average(tiny_dataset):
    loader_a = DataLoader(tiny_dataset, batch_size=16)
    loader_b = DataLoader(tiny_dataset, batch_size=16)

    client_a = FederatedClient(0, loader_a)
    client_b = FederatedClient(1, loader_b)

    model = build_model()
    result_a = client_a.local_train(model, local_epochs=1, lr=0.1)
    result_b = client_b.local_train(model, local_epochs=1, lr=0.1)

    avg_state = federated_average([result_a, result_b])

    # Equal-sized clients -> simple average.
    for k in avg_state:
        expected = (result_a.state_dict[k].float() + result_b.state_dict[k].float()) / 2
        assert torch.allclose(avg_state[k].float(), expected, atol=1e-5)


def test_one_communication_round_completes(tiny_dataset):
    loaders = [DataLoader(tiny_dataset, batch_size=16) for _ in range(3)]
    clients = [FederatedClient(i, loader) for i, loader in enumerate(loaders)]
    model = build_model()
    server = FederatedServer(model, clients)

    results = server.broadcast_and_train_round(local_epochs=1, lr=0.1, momentum=0.9)
    server.aggregate(results)
    metrics = server.evaluate(DataLoader(tiny_dataset, batch_size=32))

    assert "test_accuracy" in metrics
    assert 0.0 <= metrics["test_accuracy"] <= 1.0
