# Documenti Util Project

This project provides a simple interface for managing documents through an HTML file (`documenti.html`). Users can upload documents, view them, and download them as needed. The project is structured to separate concerns, with JavaScript handling the logic and TypeScript providing type definitions.

## Project Structure

```
documenti-util-project
├── src
│   ├── use_documenti.js       # Script to interact with documenti.html
│   └── types
│       └── index.d.ts         # Type definitions for the project
├── documenti.html             # HTML interface for document management
├── package.json                # npm configuration file
└── README.md                   # Project documentation
```

## Getting Started

To get started with the project, follow these steps:

1. **Clone the repository**:
   ```
   git clone <repository-url>
   cd documenti-util-project
   ```

2. **Install dependencies**:
   Make sure you have Node.js installed. Then run:
   ```
   npm install
   ```

3. **Run the project**:
   Open `documenti.html` in your web browser to start using the document management interface.

## Usage

- **Uploading Documents**: Use the upload button in the interface to select and upload documents.
- **Viewing Documents**: Click on the "Visualizza" button next to any document to view it in a new tab.
- **Downloading Documents**: Click on the "Scarica" button to download the document to your local machine.

## Contributing

If you would like to contribute to this project, please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.