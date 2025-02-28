document.addEventListener('DOMContentLoaded', () => {
    // Drag-and-drop для ZIP
    const zipDrop = document.getElementById('zip-drop');
    const zipInput = document.getElementById('project-zip');
    zipDrop.addEventListener('dragover', (e) => { e.preventDefault(); zipDrop.classList.add('dragover'); });
    zipDrop.addEventListener('dragleave', () => zipDrop.classList.remove('dragover'));
    zipDrop.addEventListener('drop', (e) => {
        e.preventDefault();
        zipDrop.classList.remove('dragover');
        zipInput.files = e.dataTransfer.files;
        zipDrop.textContent = zipInput.files[0].name;
    });
    zipDrop.addEventListener('click', () => zipInput.click());

    // Drag-and-drop для P8
    const p8Drop = document.getElementById('p8-drop');
    const p8Input = document.getElementById('p8-file');
    p8Drop.addEventListener('dragover', (e) => { e.preventDefault(); p8Drop.classList.add('dragover'); });
    p8Drop.addEventListener('dragleave', () => p8Drop.classList.remove('dragover'));
    p8Drop.addEventListener('drop', (e) => {
        e.preventDefault();
        p8Drop.classList.remove('dragover');
        p8Input.files = e.dataTransfer.files;
        p8Drop.textContent = p8Input.files[0].name;
    });
    p8Drop.addEventListener('click', () => p8Input.click());

    // Автозаполнение полей
    document.getElementById('fill-btn').addEventListener('click', () => {
        const data = document.getElementById('fill-data').value.split('\n').map(line => line.trim());
        const fields = ['app_name', 'bundle_id', 'apple_id', 'issuer_id', 'key_id'];
        data.forEach((line, i) => {
            if (i < fields.length) {
                const field = document.querySelector(`input[name="${fields[i]}"]`);
                if (field) field.value = line;
            }
        });
    });
});