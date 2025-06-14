#!/bin/bash
set -e

# Update system packages
sudo apt-get update

# Install Python 3.12 and pip if not available
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip

# Install PostgreSQL and development headers
sudo apt-get install -y postgresql postgresql-contrib postgresql-server-dev-all

# Install system dependencies for Python packages
sudo apt-get install -y build-essential libssl-dev libffi-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# Install GUI libraries for PySide6 (but we'll skip GUI tests)
sudo apt-get install -y libegl1-mesa libxkbcommon0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-xinerama0 libxcb-xfixes0 || true

# Install git for pgvector compilation
sudo apt-get install -y git cmake

# Install uv package manager if not already installed
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> $HOME/.profile
fi
export PATH="$HOME/.local/bin:$PATH"

# Create and activate virtual environment using uv
cd /mnt/persist/workspace
uv venv .venv
echo 'source /mnt/persist/workspace/.venv/bin/activate' >> $HOME/.profile
source .venv/bin/activate

# Install dependencies using uv
uv sync

# Manually install pgvector extension
cd /tmp
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Configure PostgreSQL to accept connections
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/14/main/postgresql.conf
sudo sed -i "s/#port = 5432/port = 5432/" /etc/postgresql/14/main/postgresql.conf

# Configure PostgreSQL authentication
echo "local   all             all                                     trust" | sudo tee /etc/postgresql/14/main/pg_hba.conf
echo "host    all             all             127.0.0.1/32            trust" | sudo tee -a /etc/postgresql/14/main/pg_hba.conf
echo "host    all             all             ::1/128                 trust" | sudo tee -a /etc/postgresql/14/main/pg_hba.conf

# Start PostgreSQL service manually (since systemd is not available)
sudo -u postgres /usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main -l /var/log/postgresql/postgresql-14-main.log start || true

# Wait for PostgreSQL to start
sleep 10

# Create test database and user
sudo -u postgres createdb localknowledge_test || true
sudo -u postgres psql -c "CREATE USER testuser WITH PASSWORD 'testpass';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE localknowledge_test TO testuser;" || true
sudo -u postgres psql -d localknowledge_test -c "CREATE EXTENSION IF NOT EXISTS vector;" || true

# Create .env.test file for testing
cat > .env.test << EOF
LK_DB_HOST=localhost
LK_DB_PORT=5432
LK_DB_NAME=localknowledge_test
LK_DB_USER=testuser
LK_DB_PASSWORD=testpass
POSTGRES_DB=localknowledge_test
POSTGRES_USER=testuser
POSTGRES_PASSWORD=testpass
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
OLLAMA_HOST=http://localhost:11434
LK_PDF_DIR=/tmp/test_pdfs
LOG_LEVEL=INFO
DOTENV_FILE=.env.test
EOF

# Set environment variables for the current session
export LK_DB_HOST=localhost
export LK_DB_PORT=5432
export LK_DB_NAME=localknowledge_test
export LK_DB_USER=testuser
export LK_DB_PASSWORD=testpass
export POSTGRES_DB=localknowledge_test
export POSTGRES_USER=testuser
export POSTGRES_PASSWORD=testpass
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export OLLAMA_HOST=http://localhost:11434
export LK_PDF_DIR=/tmp/test_pdfs
export LOG_LEVEL=INFO
export DOTENV_FILE=.env.test

# Add environment variables to profile for persistence
echo 'export LK_DB_HOST=localhost' >> $HOME/.profile
echo 'export LK_DB_PORT=5432' >> $HOME/.profile
echo 'export LK_DB_NAME=localknowledge_test' >> $HOME/.profile
echo 'export LK_DB_USER=testuser' >> $HOME/.profile
echo 'export LK_DB_PASSWORD=testpass' >> $HOME/.profile
echo 'export POSTGRES_DB=localknowledge_test' >> $HOME/.profile
echo 'export POSTGRES_USER=testuser' >> $HOME/.profile
echo 'export POSTGRES_PASSWORD=testpass' >> $HOME/.profile
echo 'export POSTGRES_HOST=localhost' >> $HOME/.profile
echo 'export POSTGRES_PORT=5432' >> $HOME/.profile
echo 'export OLLAMA_HOST=http://localhost:11434' >> $HOME/.profile
echo 'export LK_PDF_DIR=/tmp/test_pdfs' >> $HOME/.profile
echo 'export LOG_LEVEL=INFO' >> $HOME/.profile
echo 'export DOTENV_FILE=.env.test' >> $HOME/.profile

# Create test PDF directory
mkdir -p /tmp/test_pdfs

# Install Ollama (for AI functionality tests)
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service in background
ollama serve &
sleep 10

# Pull required models for tests (if Ollama is working)
ollama pull snowflake-arctic-embed2:latest || echo "Warning: Could not pull embedding model"
ollama pull gemma3:4b || echo "Warning: Could not pull QA model"

echo "Setup completed successfully"