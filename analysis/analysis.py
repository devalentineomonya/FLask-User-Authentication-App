import matplotlib.pyplot as plt
import numpy as np

# ============================================
# DATA - Fill in your teammates numbers here
# ============================================

# Your data (Helm vs YAML)
yaml_deployment_time = 0.868
helm_deployment_time = 1.313
yaml_files = 4
helm_files = 5
yaml_errors = 1
helm_errors = 0
yaml_hardcoded = 10
helm_hardcoded = 0

# Teammates data (fill when received)
jenkins_time = 0      # Person 2 will give you this
github_actions_time = 0  # Person 2 will give you this
jenkins_failures = 0  # Person 2 will give you this
github_actions_failures = 0  # Person 2 will give you this
docker_deploy_time = 0   # Person 3 will give you this
k8s_deploy_time = 0      # Person 3 will give you this

# ============================================
# GRAPH 1 - Helm vs YAML Deployment Time
# ============================================
fig, ax = plt.subplots(figsize=(8, 5))
tools = ['YAML Manifests', 'Helm Chart']
times = [yaml_deployment_time, helm_deployment_time]
colors = ['#e74c3c', '#2ecc71']
bars = ax.bar(tools, times, color=colors, width=0.4)
ax.set_title('Deployment Time: YAML vs Helm', fontsize=14, fontweight='bold')
ax.set_ylabel('Time (seconds)')
ax.set_xlabel('Deployment Method')
for bar, time in zip(bars, times):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f'{time}s', ha='center', fontweight='bold')
plt.tight_layout()
plt.savefig('graph1_deployment_time.png', dpi=150)
plt.show()
print("Graph 1 saved!")

# ============================================
# GRAPH 2 - Helm vs YAML Errors
# ============================================
fig, ax = plt.subplots(figsize=(8, 5))
errors = [yaml_errors, helm_errors]
bars = ax.bar(tools, errors, color=colors, width=0.4)
ax.set_title('Deployment Errors: YAML vs Helm', fontsize=14, fontweight='bold')
ax.set_ylabel('Number of Errors')
ax.set_xlabel('Deployment Method')
for bar, error in zip(bars, errors):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            str(error), ha='center', fontweight='bold')
plt.tight_layout()
plt.savefig('graph2_errors.png', dpi=150)
plt.show()
print("Graph 2 saved!")

# ============================================
# GRAPH 3 - Hardcoded Values Comparison
# ============================================
fig, ax = plt.subplots(figsize=(8, 5))
hardcoded = [yaml_hardcoded, helm_hardcoded]
bars = ax.bar(tools, hardcoded, color=colors, width=0.4)
ax.set_title('Hardcoded Values: YAML vs Helm', fontsize=14, fontweight='bold')
ax.set_ylabel('Number of Hardcoded Values')
ax.set_xlabel('Deployment Method')
for bar, val in zip(bars, hardcoded):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            str(val), ha='center', fontweight='bold')
plt.tight_layout()
plt.savefig('graph3_hardcoded.png', dpi=150)
plt.show()
print("Graph 3 saved!")

# ============================================
# GRAPH 4 - CI/CD Pipeline Time Comparison
# (Fill when you get data from Person 2)
# ============================================
fig, ax = plt.subplots(figsize=(8, 5))
cicd_tools = ['Jenkins', 'GitHub Actions']
cicd_times = [jenkins_time, github_actions_time]
colors2 = ['#3498db', '#9b59b6']
bars = ax.bar(cicd_tools, cicd_times, color=colors2, width=0.4)
ax.set_title('CI/CD Pipeline Time: Jenkins vs GitHub Actions',
             fontsize=14, fontweight='bold')
ax.set_ylabel('Time (seconds)')
ax.set_xlabel('CI/CD Tool')
for bar, time in zip(bars, cicd_times):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f'{time}s', ha='center', fontweight='bold')
plt.tight_layout()
plt.savefig('graph4_cicd_time.png', dpi=150)
plt.show()
print("Graph 4 saved!")

# ============================================
# GRAPH 5 - Docker vs Kubernetes Deploy Time
# (Fill when you get data from Person 3)
# ============================================
fig, ax = plt.subplots(figsize=(8, 5))
deploy_tools = ['Docker', 'Kubernetes']
deploy_times = [docker_deploy_time, k8s_deploy_time]
colors3 = ['#e67e22', '#1abc9c']
bars = ax.bar(deploy_tools, deploy_times, color=colors3, width=0.4)
ax.set_title('Deployment Time: Docker vs Kubernetes',
             fontsize=14, fontweight='bold')
ax.set_ylabel('Time (seconds)')
ax.set_xlabel('Deployment Method')
for bar, time in zip(bars, deploy_times):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
            f'{time}s', ha='center', fontweight='bold')
plt.tight_layout()
plt.savefig('graph5_docker_vs_k8s.png', dpi=150)
plt.show()
print("Graph 5 saved!")

print("\n✅ All graphs generated successfully!")
print("📊 Files saved in the analysis folder")