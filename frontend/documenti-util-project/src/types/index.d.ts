// This file defines TypeScript types for the project, providing type definitions for any objects or functions used in use_documenti.js.

interface DocumentItem {
    name: string;
    date: string;
    url: string;
}

interface User {
    email: string;
    role: string;
}

type UploadFileHandler = (file: File) => void;

type DocumentListHandler = (documents: DocumentItem[]) => void;