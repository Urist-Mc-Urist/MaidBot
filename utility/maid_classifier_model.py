import torch
import torch.nn as nn
from PIL import Image
from torchvision.transforms import ToTensor
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class MCNN(nn.Module):
    def __init__(self):
        super(MCNN, self).__init__()

        # Convolution layers
        self.conv1 = nn.Conv2d(3, 64, 3, 1, 1)
        self.bn1 = nn.BatchNorm2d(64)
        
        self.conv2 = nn.Conv2d(64, 128, 3, 1, 1)
        self.bn2 = nn.BatchNorm2d(128)
        
        self.conv3 = nn.Conv2d(128, 256, 3, 1, 1)
        self.bn3 = nn.BatchNorm2d(256)

        self.conv4 = nn.Conv2d(256, 512, 3, 1, 1) # Added another convolutional layer
        self.bn4 = nn.BatchNorm2d(512)

        # Pooling layer
        self.pool = nn.MaxPool2d(2, 2)

        # Fully connected layers
        self.fc1 = nn.Linear(100352, 2048)
        self.fc2 = nn.Linear(2048, 1024)
        self.fc3 = nn.Linear(1024, 512)
        self.fc4 = nn.Linear(512, 256)
        self.fc5 = nn.Linear(256, 2)  # Two classes

        # Activation and dropout
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)

    def forward(self, pixel_values, labels=None):
        x = self.pool(self.relu(self.bn1(self.conv1(pixel_values))))
        x = self.pool(self.relu(self.bn2(self.conv2(x))))
        x = self.pool(self.relu(self.bn3(self.conv3(x))))
        x = self.pool(self.relu(self.bn4(self.conv4(x)))) # Pass through the added conv layer

        x = x.view(x.size(0), -1)  # flatten
        x = self.dropout(self.relu(self.fc1(x)))
        x = self.dropout(self.relu(self.fc2(x)))
        x = self.dropout(self.relu(self.fc3(x)))
        x = self.dropout(self.relu(self.fc4(x)))
        logits = self.fc5(x)

        loss = None
        if labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits.view(-1, 2), labels.view(-1))

        if loss is not None:
            return logits, loss.item()
        else:
            return logits, None
        
def preprocess_image(img, desired_size=224):
    im = img

    # Resize and pad the image
    old_size = im.size
    ratio = float(desired_size) / max(old_size)
    new_size = tuple([int(x*ratio) for x in old_size])
    im = im.resize(new_size)

    # Create a new image and paste the resized on it
    new_im = Image.new("RGB", (desired_size, desired_size), "white")
    new_im.paste(im, ((desired_size-new_size[0])//2,
                      (desired_size-new_size[1])//2))
    return new_im

def predict_image(image, model):
    # Ensure model is in eval mode
    model.eval()

    # Convert image to tensor
    transform = ToTensor()
    input_tensor = transform(image)
    input_batch = input_tensor.unsqueeze(0)

    # Move tensors to the right device
    input_batch = input_batch.to(device)

    # Forward pass of the image through the model
    output = model(input_batch)

    # Convert model output to probabilities using softmax
    probabilities = torch.nn.functional.softmax(output[0], dim=1)

    return probabilities.cpu().detach().numpy()