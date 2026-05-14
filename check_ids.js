const fs = require('fs');
const html = fs.readFileSync('templates/index.html', 'utf8');
const ids = html.match(/id="([^"]+)"/g);
const idMap = {};
const duplicates = [];

if (ids) {
    ids.forEach(idStr => {
        const id = idStr.match(/"([^"]+)"/)[1];
        if (idMap[id]) {
            duplicates.push(id);
        }
        idMap[id] = (idMap[id] || 0) + 1;
    });
}

if (duplicates.length > 0) {
    console.log('Duplicate IDs found:', [...new Set(duplicates)]);
} else {
    console.log('No duplicate IDs found.');
}
