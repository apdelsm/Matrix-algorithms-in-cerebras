# LU factorization without pivoting

Here you can find the implementation for a matrix A in LU in cerebras. This implementation not implement pivoting and also assume one element per PE.
The main idea is exposed in the next image, where is described the flow of the data in a 3x3 matrix, where colored arrows represents the communication channels used, if an arrow is thicker than others, it means that the channel is being used, emmiting the data labeled near the arrow.

![Alt text](./cerebras_lu.png "LU_cerebras")

4 colors have been used:
 - The blue color is used to emmit a signal horizontally, when a PE receive a value from this color, it send his self value down for the elimination step.
 - The purple color is used vertically in the elimination step, when a PE receive a value from this color, it store it and perform the elimination if able.
 - The green color is for the division step, when a PE receive a value from this color, it divide the value stored in the PE by the value received and then send the result to the right.
 - The red color is used horizontally in the elimination step, when a PE receive a value from this color, it store it and perdorm the elimination if able.

A PE is able to perform the elimination step when have been received both values necessaries for it, one from the purple color (north) and one from the red color (west). After this, if the PE is in the diagonal and have been performed an amount of elimination steps equal to it column number (starting from 0), it will start a division step, sending self value to the south using the green color and will send a signal (self value in this case) to the east using the blue color.