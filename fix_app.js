const fs = require('fs');
const path = 'static/js/app.js';
let content = fs.readFileSync(path, 'utf8');

// Fix Facebook Card Class
const oldFb = '            <div class="oracle-score-container glass-panel">';
const newFb = '            <div class="oracle-score-container glass-panel facebook-card">';
content = content.replace(oldFb, newFb);

// Fix Instagram Hashtags
const oldInsta = '<textarea class="draft-edit field-caption" rows="4">${post.caption || \'\'}</textarea>';
const newInsta = '<textarea class="draft-edit field-caption" rows="4">${post.caption || \'\'}</textarea>\n                    <label style="font-size:0.8em; opacity:0.7; margin-top:5px;">Hashtags:</label>\n                    <textarea class="draft-edit field-hashtags" rows="2">${post.hashtags || \'\'}</textarea>';
content = content.replace(oldInsta, newInsta);

fs.writeFileSync(path, content, 'utf8');
console.log('✅ app.js fixed with Node script.');
