import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { LabmindApiService } from '../../services/labmind-api.service';

@Component({
  selector: 'app-verification',
  imports: [],
  templateUrl: './verification.component.html',
  styleUrl: './verification.component.css'
})
export class VerificationComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private api = inject(LabmindApiService);

  taskId = '';
  task: any = null;
  showCustomInput = false;
  customValue = '';
  isSubmitting = false;
  errorMessage = '';

  ngOnInit() {
    this.taskId = this.route.snapshot.paramMap.get('id') || '';
    const stateTask = history.state?.task;

    if (stateTask && stateTask.task_id === this.taskId) {
      this.task = stateTask;
    } else if (this.taskId) {
      this.api.getTask(this.taskId).subscribe({
        next: (task) => this.handleTaskUpdate(task),
        error: (err) => {
          this.router.navigate(['/erreur'], { state: { error: this.api.formatError(err) } });
        }
      });
    }
  }

  get optionsList(): string[] {
    const opts: string[] = [...(this.task?.pending_question?.options || [])];
    if (!opts.includes('je ne sais pas')) {
      opts.push('je ne sais pas');
    }
    return opts;
  }

  get matchedParameter(): any {
    const code = this.task?.pending_question?.code;
    return this.task?.parameters?.find((p: any) => p.code === code) || null;
  }

  onOptionClick(option: string) {
    if (option === 'autre') {
      this.showCustomInput = true;
      this.errorMessage = '';
      return;
    }
    this.sendAnswer(option);
  }

  sendAnswer(answer: string) {
    if (!this.task?.pending_question || this.isSubmitting) return;

    this.isSubmitting = true;
    this.errorMessage = '';

    this.api
      .submitAnswer(this.taskId, this.task.pending_question.question_id, answer)
      .subscribe({
        next: (updatedTask) => {
          this.isSubmitting = false;
          this.handleTaskUpdate(updatedTask);
        },
        error: (err) => {
          this.isSubmitting = false;
          const formatted = this.api.formatError(err);
          if (err?.status === 422 || formatted.code === 'invalid_answer') {
            this.errorMessage = formatted.message;
          } else if (err?.status === 409 || formatted.code === 'invalid_state') {
            this.router.navigate(['/attente', this.taskId]);
          } else {
            this.router.navigate(['/erreur'], { state: { error: formatted } });
          }
        }
      });
  }

  private handleTaskUpdate(updatedTask: any) {
    if (!updatedTask || !updatedTask.status) {
      this.router.navigate(['/attente', this.taskId]);
      return;
    }

    if (updatedTask.status === 'waiting_for_user' && updatedTask.pending_question) {
      this.task = updatedTask;
      this.showCustomInput = false;
      this.customValue = '';
      return;
    }

    if (updatedTask.status === 'done') {
      this.router.navigate(['/resultats', this.taskId], { state: { task: updatedTask } });
      return;
    }

    if (updatedTask.status === 'error') {
      const firstError = updatedTask.errors?.[0] || {
        code: 'internal_error',
        message: "L'analyse n'a pas pu aboutir."
      };
      this.router.navigate(['/erreur'], { state: { error: firstError } });
      return;
    }

    this.router.navigate(['/attente', this.taskId]);
  }

  supprimerDonnees() {
    this.api.deleteTask(this.taskId).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) =>
        this.router.navigate(['/erreur'], { state: { error: this.api.formatError(err) } })
    });
  }
}
