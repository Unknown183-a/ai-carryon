import torch
from torch.utils.data import TensorDataset

from src.federated.client import ClientUpdate, FederatedClient
from src.federated.fedavg import fedavg
from src.models.cnn import build_model


def test_fedavg_weighted_average():
    m1, m2 = build_model("cnn"), build_model("cnn")
    for p in m2.parameters():
        p.data += 1.0  # make m2's weights distinguishable from m1's

    u1 = ClientUpdate(client_id=0, state_dict=m1.state_dict(), num_samples=10, train_loss=0.0)
    u2 = ClientUpdate(client_id=1, state_dict=m2.state_dict(), num_samples=30, train_loss=0.0)

    avg_state = fedavg([u1, u2])
    key = next(iter(avg_state))
    expected = 0.25 * m1.state_dict()[key] + 0.75 * m2.state_dict()[key]
    assert torch.allclose(avg_state[key], expected, atol=1e-5)


def test_client_local_train_and_evaluate_run():
    x = torch.randn(16, 1, 28, 28)
    y = torch.randint(0, 10, (16,))
    ds = TensorDataset(x, y)
    client = FederatedClient(client_id=0, dataset=ds, batch_size=4)
    model = build_model("cnn")

    update = client.local_train(model, epochs=1, lr=0.01)
    assert update.num_samples == 16
    assert isinstance(update.train_loss, float)

    metrics = client.evaluate(model)
    assert 0.0 <= metrics["accuracy"] <= 1.0
