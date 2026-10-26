# Cloud and Containers

Source describes intent, not the live deployment. Separate what the
repository proves from what depends on account policy, overlays or
runtime attachment; the second kind is `HEURISTIC` until observed.

## Workload Identity

- Map each workload's identity to the operations and resources it can
  touch. Broad policy is a finding when lower-trust input can steer an
  action it permits.
- Role assumption and token exchange must bind the source account,
  repository, branch, namespace or workload; an unscoped trust policy
  lets anyone matching the provider assume the role.
- Application authorization is separate from cloud IAM: headers, tags
  or labels a caller can set are not identity.

## Network Exposure

- Admin, debug, metrics and internal APIs bound to a public interface
  or routed through public ingress.
- Backends that trust identity headers from any peer instead of only
  the proxy that strips them.
- User-controlled URLs that reach the instance metadata service or
  internal services with the workload's credentials.

## Containers and Orchestration

- Privileged mode, added capabilities, host namespaces, host paths,
  device mounts or the container runtime socket cross into the node.
- Service-account tokens mounted into workloads that do not need them.
- Policy enforced on one deployment path but not on another (jobs,
  upgrades, restores).
- Network or admission policy keyed on labels a lower-trust principal
  can set.
- Images pinned by mutable tag rather than digest.

## Configuration

- Render the final configuration of each maintained environment; a
  development value, chart default or overlay can disable
  authentication, TLS or tenant scope in production.
- Secrets in environment dumps, process arguments, broad volumes or
  crash reports readable by another workload.
- Failure to mount or refresh a credential must not fall back to a
  weaker identity mode.

## Storage and Events

- Bucket policies and signed URLs bind principal, operation, object
  prefix and expiry.
- Functions triggered by events verify the provider-signed envelope,
  not fields in the event body.
