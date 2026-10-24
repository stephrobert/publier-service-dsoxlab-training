# Scenario

The application is already published through HAProxy, and a Prometheus
instance is ready to scrape it. The metrics listener returns no metrics, and
both monitoring interfaces are reachable from other hosts.

## Mission

Configure an HTTP Prometheus exporter for HAProxy, restrict both monitoring
interfaces to the host, and make Prometheus report a healthy scrape and
backend.

The public application must remain available throughout the change.
