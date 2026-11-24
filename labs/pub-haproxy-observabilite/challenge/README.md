# Monitor HAProxy with Prometheus

## The situation

The application is already published through HAProxy, and a Prometheus
instance is ready to scrape it. The metrics listener returns no metrics, and
both monitoring interfaces are reachable from other hosts.

## Mission

Configure an HTTP Prometheus exporter for HAProxy, restrict both monitoring
interfaces to the host, and make Prometheus report a healthy scrape and
backend.

The public application must remain available throughout the change.

## What is asked

### Criteria

- The application remains available through HAProxy.
- Prometheus successfully scrapes HAProxy metrics and reports the backend as
  healthy.
- The exporter is reachable on the VM itself but not from another host.
- The Prometheus web interface is not exposed to other hosts.

The reference solution is not included in the guides.
