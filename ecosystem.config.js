module.exports = {
  apps: [
    {
      name: 'turnstile-solver',
      script: './start.sh',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      restart_delay: 2000,
      env: {
        NODE_ENV: 'production',
        PORT: 6767,
        HEADLESS: 'false',
        // Configure the browser context pool size here (e.g. 5, 10, 20):
        POOL_SIZE: 5
      }
    }
  ]
};
