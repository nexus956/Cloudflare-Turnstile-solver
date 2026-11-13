module.exports = {
  apps: [
    {
      name: "turnstile-solver",
      script: "./start.sh",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      restart_delay: 2000,
      env: {
        NODE_ENV: "production",
        PORT: 6969,
        POOL_SIZE: 50,
        MAX_CONCURRENT_HEADFUL: 10,
        MAX_CONCURRENT_HEADLESS: 20
      }
    }
  ]
};
