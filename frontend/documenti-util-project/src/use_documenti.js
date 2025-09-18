// filepath: documenti-util-project/src/use_documenti.js
document.addEventListener('DOMContentLoaded', function() {
    const fileUpload = document.getElementById("fileUpload");
    const docList = document.getElementById("docList");

    fileUpload.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            const li = document.createElement("li");
            li.className = "doc-item";

            const info = document.createElement("div");
            info.className = "doc-info";
            info.innerHTML = `
                <div class="doc-title">${file.name}</div>
                <div class="doc-date">${new Date().toLocaleString()}</div>
            `;

            const actions = document.createElement("div");
            actions.className = "doc-actions";

            const viewBtn = document.createElement("button");
            viewBtn.className = "btn-view";
            viewBtn.textContent = "👁 Visualizza";
            viewBtn.addEventListener("click", () => {
                const url = URL.createObjectURL(file);
                window.open(url, "_blank");
            });

            const downloadBtn = document.createElement("button");
            downloadBtn.className = "btn-download";
            downloadBtn.textContent = "⬇ Scarica";
            downloadBtn.addEventListener("click", () => {
                const url = URL.createObjectURL(file);
                const a = document.createElement("a");
                a.href = url;
                a.download = file.name;
                a.click();
                URL.revokeObjectURL(url);
            });

            actions.appendChild(viewBtn);
            actions.appendChild(downloadBtn);

            li.appendChild(info);
            li.appendChild(actions);
            docList.appendChild(li);
        }
    });
});