from pathlib import Path
from os import environ

import torch as t
import torch.nn as nn
import torch.optim as optim

from agents.base import BaseAgent
from torch.utils.data import DataLoader
from datasets.GSC import GoogleSpeechCommandDataset
from losses.NLL import NegativeLogLikelihood
from models.BasicConvNet import BasicNet
from models.BasicRecurrentNet import BasicRNN



class GSCAgent(BaseAgent):

    def __init__(self, config):
        super().__init__(config)

        self.model = BasicRNN()
        if self.cuda:
            self.model = nn.DataParallel(self.model)
            self.model = self.model.to(self.device)

        self.loss = NegativeLogLikelihood()
        self.loss = self.loss.to(self.device)

        self.optimizer = optim.SGD(self.model.parameters(), lr=self.config.learning_rate, momentum=self.config.momentum)

        assert environ["GSCPATH"]
        self.dataloader_train = DataLoader(GoogleSpeechCommandDataset(
            Path(environ["GSCPATH"]), mode="train"),
            batch_size=self.config.batch_size, shuffle=True, pin_memory=self.cuda, sampler=None)
        self.dataloader_test = DataLoader(GoogleSpeechCommandDataset(
            Path(environ["GSCPATH"]), mode="test"),
            batch_size=self.config.batch_size, shuffle=False, pin_memory=self.cuda, sampler=None)
        self.dataloader_valid = DataLoader(GoogleSpeechCommandDataset(
            Path(environ["GSCPATH"]), mode="valid"),
            batch_size=self.config.batch_size, shuffle=False, pin_memory=self.cuda, sampler=None)

    def init(self):
        pass

    def train_one_epoch(self):
        self.model.train()
        for batch_id, (x, y) in enumerate(self.dataloader_train):
            if self.cuda:
                x, y = x.to(self.device), y.to(self.device)
            self.optimizer.zero_grad()
            output = self.model(x)
            loss = self.loss(output, y)
            loss.backward()
            self.optimizer.step()
            print('Train Epoch: {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}'.format(
                self.current_epoch,
                batch_id * len(x),
                len(self.dataloader_train.dataset),
                100. * batch_id / len(self.dataloader_train),
                loss.data.item()))

    def validate(self, mode="test"):
        assert mode in ["test", "valid"]
        if mode == "test":
            loader = self.dataloader_test
        else:
            loader = self.dataloader_valid
        self.model.eval()
        test_loss = 0
        correct_predictions = 0
        with t.no_grad():
            for x, y in loader:
                x, y = x.to(self.device), y.to(self.device)
                output = self.model(x)
                test_loss += self.loss(output, y).data.item()
                pred = output.max(1, keepdim=True)[1]
                correct_predictions += pred.eq(y.view_as(pred)).sum().item()
        print(f"Testing results after epoch {self.current_epoch}:\n"
              f"Accuracy: {correct_predictions / len(loader.dataset)}\n"
              f"Loss: {test_loss}")

    def finalize(self):
        pass
