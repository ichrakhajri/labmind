import { Component, OnInit, OnDestroy, inject, PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { LabmindApiService } from '../../services/labmind-api.service';

@Component({
  selector: 'app-attente',
  imports: [],
  templateUrl: './attente.component.html',
  styleUrl: './attente.component.css'
})
export class AttenteComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(LabmindApiService);
  private platformId = inject(PLATFORM_ID);

  taskId = '';
  status = 'received';
  disclaimer = '';
  private pollTimer: ReturnType<typeof setTimeout> | null = null;
  private destroyed = false;

  ngOnInit() {
    this.taskId = this.route.snapshot.paramMap.get('id') || '';
    if (!this.taskId) {
      this.router.navigate(['/erreur'], {
        state: { error: { code: 'task_not_found', message: 'Identifiant de tâche manquant.' } }
      });
      return;
    }

    if (isPlatformBrowser(this.platformId)) {
      this.pollOnce();
    }
  }

  ngOnDestroy() {
    this.destroyed = true;
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
    }
  }

  private pollOnce() {
    if (this.destroyed) return;

    this.api.getTask(this.taskId).subscribe({
      next: (task) => {
        if (this.destroyed) return;
        this.status = task.status;
        this.disclaimer = task.disclaimer || '';

        if (task.status === 'waiting_for_user') {
          this.router.navigate(['/verification', this.taskId], { state: { task } });
          return;
        }

        if (task.status === 'done') {
          this.router.navigate(['/resultats', this.taskId], { state: { task } });
          return;
        }

        if (task.status === 'error') {
          const firstError = task.errors?.[0] || {
            code: 'internal_error',
            message: "L'analyse n'a pas pu aboutir."
          };
          this.router.navigate(['/erreur'], { state: { error: firstError } });
          return;
        }

        this.pollTimer = setTimeout(() => this.pollOnce(), 2000);
      },
      error: (err) => {
        if (this.destroyed) return;
        this.router.navigate(['/erreur'], {
          state: { error: this.api.formatError(err) }
        });
      }
    });
  }
}
