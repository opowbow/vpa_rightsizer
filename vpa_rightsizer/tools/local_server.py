import http.server
import os
import socketserver
import sys


class VPAReportHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Clean path from query strings or hashes
        clean_path = path.split('?')[0].split('#')[0]

        # If it starts with /vpa-, it's a manifest request
        if clean_path.startswith('/vpa-'):
            full_path = os.path.join(os.getcwd(), clean_path.lstrip('/'))
            if os.path.exists(full_path) and os.path.isfile(full_path):
                return full_path

        # If it exists under public directory
        public_path = os.path.join(os.getcwd(), "public", clean_path.lstrip('/'))
        if os.path.exists(public_path) and os.path.isfile(public_path):
            return public_path

        # Fallback to index.html for SPA routing
        return os.path.join(os.getcwd(), "public", "index.html")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 local_server.py <port> <web_report_dir>")
        sys.exit(1)

    port = int(sys.argv[1])
    web_report_dir = sys.argv[2]

    # Change current working directory to web_report_dir so translate_path functions correctly
    os.chdir(web_report_dir)

    # Configure socket reuse to prevent "Address already in use" errors during quick restarts
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("", port), VPAReportHandler) as httpd:
        print(f"Local server listening on port {port} (serving from {web_report_dir})")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down local server...")
            httpd.shutdown()

if __name__ == "__main__":
    main()
