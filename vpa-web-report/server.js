const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const port = process.env.PORT || 80;

// Serve static files from public/
app.use(express.static(path.join(__dirname, 'public')));

// Serve GKE manifests from any vpa-* directories
const rootDir = __dirname;
try {
  fs.readdirSync(rootDir).forEach(file => {
    const fullPath = path.join(rootDir, file);
    if (file.startsWith('vpa-') && fs.statSync(fullPath).isDirectory()) {
      app.use('/' + file, express.static(fullPath));
      console.log(`Serving manifests from /${file}`);
    }
  });
} catch (err) {
  console.error("Error reading root directory for vpa-* folders:", err);
}

// Fallback to index.html for SPA routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(port, () => {
  console.log(`Server listening on port ${port}`);
});
